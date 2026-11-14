// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./AuthorityGuard.sol";

/**
 * @title SocialRecoveryWallet
 * @notice Demonstrates a full social recovery wallet protected by AuthorityGuard.
 */
contract SocialRecoveryWallet is AuthorityGuard {
    // Current Wallet Authority State
    address public owner;
    address[] public guardians;
    address[] public modules;

    // Recovery Timelock State
    address public pendingNewOwner;
    uint256 public recoveryExecutionTime;
    bool public isRecoveryPending;

    uint256 public constant RECOVERY_TIMELOCK = 24 hours;

    modifier onlyOwner() {
        require(msg.sender == owner, "Unauthorized: Caller is not Owner");
        _;
    }

    constructor(address _initialOwner, address[] memory _initialGuardians) {
        require(_initialOwner != address(0), "Invalid owner");
        owner = _initialOwner;
        guardians = _initialGuardians;

        // Initialize Authority Epoch #1
        bytes32 initialHash = _computeAuthorityHash(owner, guardians, modules);
        _updateAuthorityEpoch(initialHash);
    }

    // =========================================================================
    // GUARDED BATCH EXECUTION
    // =========================================================================

    /**
     * @notice Executes multi-call batch on behalf of the owner.
     * @dev Protected by `guardBatchExecution`. Reverts if any callee attempts
     *      to manipulate recovery state or authority mid-batch.
     */
    function executeBatch(
        address[] calldata targets,
        uint256[] calldata values,
        bytes[] calldata data
    ) external payable onlyOwner guardBatchExecution {
        require(
            targets.length == values.length && values.length == data.length,
            "Mismatched array lengths"
        );

        for (uint256 i = 0; i < targets.length; i++) {
            (bool success, bytes memory returnData) = targets[i].call{value: values[i]}(data[i]);
            require(success, string(returnData));
        }
    }

    // =========================================================================
    // RECOVERY WORKFLOW (CANDIDE / SOUL WALLET PATTERN)
    // =========================================================================

    /**
     * @notice Initiates a social recovery request to transfer ownership.
     */
    function initiateRecovery(address newOwner) external {
        require(newOwner != address(0) && newOwner != owner, "Invalid candidate owner");
        isRecoveryPending = true;
        pendingNewOwner = newOwner;
        recoveryExecutionTime = block.timestamp + RECOVERY_TIMELOCK;
    }

    /**
     * @notice Permissionless finalization: anyone (relayer/user) can finalize once timelock passes.
     * @dev PROTECTED BY `disallowDuringBatch`:
     *      If an attacker tries to call this via a reentrancy callback during `executeBatch()`,
     *      it reverts with `AuthorityInFlux()`!
     */
    function finalizeRecovery() external disallowDuringBatch {
        require(isRecoveryPending, "No recovery pending");
        require(block.timestamp >= recoveryExecutionTime, "Recovery timelock has not expired");

        // 1. CHECKS & EFFECTS (CEI)
        owner = pendingNewOwner;
        isRecoveryPending = false;
        pendingNewOwner = address(0);

        // 2. BUMP AUTHORITY EPOCH
        bytes32 newAuthHash = _computeAuthorityHash(owner, guardians, modules);
        _updateAuthorityEpoch(newAuthHash);
    }

    /// @notice Allows contract to receive ETH.
    receive() external payable {}
}