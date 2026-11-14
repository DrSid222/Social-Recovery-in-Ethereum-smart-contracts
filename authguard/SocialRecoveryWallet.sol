// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./AuthorityGuard.sol";

/**
 * @title SocialRecoveryWallet
 * @notice Minimal social recovery wallet protected by AuthorityGuard.
 *         Guardians propose/support a new owner; after the timelock AND once the
 *         guardian threshold is met, anyone may finalize (permissionless, like
 *         Candide / Soul Wallet). The owner can cancel while pending.
 * @dev Demo contract: guardian set and threshold are fixed at construction.
 */
contract SocialRecoveryWallet is AuthorityGuard {
    // ---------------------------------------------------------------------
    // ERRORS
    // ---------------------------------------------------------------------
    error NotOwner();
    error NotGuardian();
    error InvalidOwner();
    error InvalidGuardian();
    error InvalidThreshold();
    error MismatchedArrays();
    error BatchCallFailed(uint256 index);
    error RecoveryAlreadyPending();
    error NoRecoveryPending();
    error AlreadySupported();
    error TimelockNotExpired();
    error ThresholdNotMet();

    // ---------------------------------------------------------------------
    // EVENTS
    // ---------------------------------------------------------------------
    event RecoveryInitiated(address indexed guardian, address indexed newOwner, uint256 executeAfter, uint256 nonce);
    event RecoverySupported(address indexed guardian, uint256 supportCount);
    event RecoveryCancelled(uint256 nonce);
    event RecoveryFinalized(address indexed oldOwner, address indexed newOwner);

    // ---------------------------------------------------------------------
    // STATE
    // ---------------------------------------------------------------------
    address public owner;
    address[] public guardians;
    address[] public modules; // kept empty in this demo; part of the authority hash
    mapping(address => bool) public isGuardian;
    uint256 public immutable threshold;

    address public pendingNewOwner;
    uint256 public recoveryExecutionTime;
    bool public isRecoveryPending;
    uint256 public recoveryNonce;
    uint256 public supportCount;
    mapping(uint256 => mapping(address => bool)) public hasSupported; // nonce => guardian => supported

    uint256 public constant RECOVERY_TIMELOCK = 24 hours;

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier onlyGuardian() {
        if (!isGuardian[msg.sender]) revert NotGuardian();
        _;
    }

    constructor(address _initialOwner, address[] memory _initialGuardians, uint256 _threshold) {
        if (_initialOwner == address(0)) revert InvalidOwner();
        if (_threshold == 0 || _threshold > _initialGuardians.length) revert InvalidThreshold();

        for (uint256 i = 0; i < _initialGuardians.length; i++) {
            address g = _initialGuardians[i];
            if (g == address(0) || g == _initialOwner || isGuardian[g]) revert InvalidGuardian();
            isGuardian[g] = true;
        }

        owner = _initialOwner;
        guardians = _initialGuardians;
        threshold = _threshold;

        // Authority Epoch #1
        _updateAuthorityEpoch(_computeAuthorityHash(owner, guardians, modules));
    }

    // ---------------------------------------------------------------------
    // GUARDED BATCH EXECUTION
    // ---------------------------------------------------------------------

    /**
     * @notice Executes a multi-call batch on behalf of the owner.
     * @dev Protected by `guardBatchExecution`. Original revert data of a failing
     *      call is bubbled up so custom errors (e.g. AuthorityInFlux) surface intact.
     */
    function executeBatch(
        address[] calldata targets,
        uint256[] calldata values,
        bytes[] calldata data
    ) external payable onlyOwner guardBatchExecution {
        if (targets.length != values.length || values.length != data.length) revert MismatchedArrays();

        for (uint256 i = 0; i < targets.length; i++) {
            (bool success, bytes memory ret) = targets[i].call{value: values[i]}(data[i]);
            if (!success) {
                if (ret.length == 0) revert BatchCallFailed(i);
                assembly {
                    revert(add(ret, 32), mload(ret))
                }
            }
        }
    }

    // ---------------------------------------------------------------------
    // RECOVERY WORKFLOW
    // ---------------------------------------------------------------------

    /// @notice A guardian proposes a new owner. Counts as that guardian's support.
    function initiateRecovery(address newOwner) external onlyGuardian disallowDuringBatch {
        if (isRecoveryPending) revert RecoveryAlreadyPending();
        if (newOwner == address(0) || newOwner == owner) revert InvalidOwner();

        recoveryNonce += 1;
        isRecoveryPending = true;
        pendingNewOwner = newOwner;
        recoveryExecutionTime = block.timestamp + RECOVERY_TIMELOCK;
        supportCount = 1;
        hasSupported[recoveryNonce][msg.sender] = true;

        emit RecoveryInitiated(msg.sender, newOwner, recoveryExecutionTime, recoveryNonce);
    }

    /// @notice Another guardian supports the pending recovery.
    function supportRecovery() external onlyGuardian disallowDuringBatch {
        if (!isRecoveryPending) revert NoRecoveryPending();
        if (hasSupported[recoveryNonce][msg.sender]) revert AlreadySupported();

        hasSupported[recoveryNonce][msg.sender] = true;
        supportCount += 1;

        emit RecoverySupported(msg.sender, supportCount);
    }

    /// @notice Owner cancels a pending recovery (e.g. a malicious guardian proposal).
    function cancelRecovery() external onlyOwner disallowDuringBatch {
        if (!isRecoveryPending) revert NoRecoveryPending();
        _clearRecovery();
        emit RecoveryCancelled(recoveryNonce);
    }

    /**
     * @notice Permissionless finalization once timelock passed and threshold met.
     * @dev PROTECTED BY `disallowDuringBatch`: a callee re-entering mid-`executeBatch`
     *      reverts with `AuthorityInFlux()`.
     */
    function finalizeRecovery() external disallowDuringBatch {
        if (!isRecoveryPending) revert NoRecoveryPending();
        if (block.timestamp < recoveryExecutionTime) revert TimelockNotExpired();
        if (supportCount < threshold) revert ThresholdNotMet();

        // CHECKS done; EFFECTS (CEI) before any event / external interaction
        address oldOwner = owner;
        address newOwner = pendingNewOwner;
        owner = newOwner;
        _clearRecovery();

        _updateAuthorityEpoch(_computeAuthorityHash(owner, guardians, modules));

        emit RecoveryFinalized(oldOwner, newOwner);
    }

    function _clearRecovery() private {
        isRecoveryPending = false;
        pendingNewOwner = address(0);
        recoveryExecutionTime = 0;
        supportCount = 0;
    }

    function guardianCount() external view returns (uint256) {
        return guardians.length;
    }

    receive() external payable {}
}
