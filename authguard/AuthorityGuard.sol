// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title AuthorityGuard
 * @author Brinda Fadadu & Siddharth Miglani
 * @notice Defends Smart-Contract Social Recovery Wallets (Argent, Candide, Soul Wallet)
 *         against Time-of-Check to Time-of-Use (TOCTOU) Authority Reentrancy attacks.
 *
 * =========================================================================================
 * ARCHITECTURAL SPECIFICATION & HOW IT WORKS:
 * =========================================================================================
 * 1. THE PROBLEM (TOCTOU Authority Reentrancy):
 *    - In modular social wallets (e.g., Candide, Soul Wallet), recovery finalization
 *      (`finalizeRecovery`, `confirmGuardianRevokation`) is permissionless so relayers
 *      can submit it on-chain after the dispute timelock expires.
 *    - However, unlike Argent which froze the wallet, modern ERC-4337 wallets lacked an
 *      execution-scoped lock.
 *    - If an owner executes a multi-call batch that interacts with an untrusted contract
 *      (e.g., ERC-777 tokensReceived hook, ERC-721 onERC721Received, or a malicious DeFi pool),
 *      the callee can re-enter the wallet's `finalizeRecovery()` mid-batch.
 *    - Subsequent calls in the batch then execute under outdated/compromised authority!
 *
 * 2. THE 4 DEFENSE PILLARS IMPLEMENTED HERE:
 *    a) Checks-Effects-Interactions (CEI): Authority transitions commit all internal state
 *       and epoch updates BEFORE emitting events or triggering external interactions.
 *    b) Authority Epoch: A packed `uint64 epochCounter` and `bytes32 authorityHash`
 *       representing the cryptographic digest of active owners, guardians, and modules.
 *    c) Wallet-Scoped Transient Execution Lock (EIP-1153):
 *       Uses `tstore` and `tload` assembly opcodes. It sets a transient flag (100 gas)
 *       during `executeBatch()`. All permissionless transition functions check this flag
 *       and revert with `AuthorityInFlux()` if invoked mid-execution.
 *    d) Snapshot-and-Verify:
 *       Takes a memory snapshot of the Authority Epoch prior to batch execution.
 *       After all external calls finish, it strictly asserts that the epoch remains
 *       identical to the snapshot; if any unexpected drift occurred, the entire batch reverts.
 * =========================================================================================
 */
abstract contract AuthorityGuard {
    // =========================================================================
    // CUSTOM ERRORS (Gas-Optimized)
    // =========================================================================

    /// @notice Thrown when a permissionless recovery function is called while a batch is executing.
    error AuthorityInFlux();

    /// @notice Thrown when post-batch epoch verification detects unauthorized authority state modification.
    error AuthorityEpochModified(
        uint64 expectedCounter,
        uint64 actualCounter,
        bytes32 expectedHash,
        bytes32 actualHash
    );

    /// @notice Thrown when reentrant execution of `executeBatch` is detected.
    error BatchReentrancyDetected();

    /// @notice Thrown if an invalid or zero authority hash is submitted.
    error InvalidAuthorityHash();

    // =========================================================================
    // EVENTS
    // =========================================================================

    event AuthorityEpochUpdated(uint64 indexed newEpochCounter, bytes32 indexed newAuthorityHash);
    event BatchExecutionStarted(uint64 snapshotEpoch, bytes32 snapshotHash);
    event BatchExecutionCompleted(uint64 currentEpoch, bytes32 currentHash);

    // =========================================================================
    // STORAGE DEFINITION & ERC-7201 NAMESPACING
    // =========================================================================

    /**
     * @dev Packed Authority Epoch struct.
     * Fits cleanly into storage:
     * - `epochCounter`: uint64 (increments on every valid authority mutation)
     * - `authorityHash`: bytes32 (keccak256 hash of owner, guardians, modules, and hooks)
     */
    struct AuthorityEpoch {
        uint64 epochCounter;
        bytes32 authorityHash;
    }

    /// @dev Main storage namespace struct to prevent collisions in upgradeable proxies.
    struct AuthorityGuardStorage {
        AuthorityEpoch epoch;
    }

    /**
     * @dev ERC-7201 Storage slot calculation:
     * keccak256(abi.encode(uint256(keccak256("authorityguard.storage.v1")) - 1)) & ~bytes32(uint256(0xff))
     */
    bytes32 private constant AUTHORITY_GUARD_STORAGE_LOCATION =
        0xd5b567210e2e1ff80ef827f748468f994b98649bb87525186452282b3b2c2800;

    /**
     * @dev EIP-1153 Transient Storage Slot for the active batch execution lock.
     * keccak256("authorityguard.transient.lock.v1")
     * Transient storage is cleared automatically at transaction completion.
     */
    bytes32 private constant TRANSIENT_LOCK_SLOT =
        0x6a0f7be5f9797f1f31f9b37cce14bb0b79da93cbbfcf199aef50974e4c274d75;

    uint256 private constant UNLOCKED = 0;
    uint256 private constant LOCKED = 1;

    // =========================================================================
    // INTERNAL STORAGE POINTERS
    // =========================================================================

    /// @dev Retrieves pointer to ERC-7201 namespaced storage.
    function _getAuthorityGuardStorage() internal pure returns (AuthorityGuardStorage storage $) {
        assembly {
            $.slot := AUTHORITY_GUARD_STORAGE_LOCATION
        }
    }

    // =========================================================================
    // EIP-1153 TRANSIENT STORAGE READ/WRITE
    // =========================================================================

    /**
     * @notice Reads the transient batch execution lock flag.
     * @return locked True if the wallet is currently mid-batch execution.
     */
    function isBatchExecuting() public view returns (bool locked) {
        assembly {
            locked := tload(TRANSIENT_LOCK_SLOT)
        }
    }

    /**
     * @dev Internal helper to set or clear the transient lock.
     */
    function _setBatchLock(uint256 state) internal {
        assembly {
            tstore(TRANSIENT_LOCK_SLOT, state)
        }
    }

    // =========================================================================
    // MODIFIERS
    // =========================================================================

    /**
     * @notice Protects batch execution functions (`executeBatch`).
     *
     * STEP-BY-STEP EXECUTION FLOW:
     * 1. Checks if wallet is already inside an active batch (reverts if reentrant).
     * 2. Sets transient lock to `LOCKED` (EIP-1153 `tstore`).
     * 3. Takes a memory snapshot of (`epochCounter`, `authorityHash`).
     * 4. Yields execution to the batch multi-call loop (`_`).
     * 5. Releases transient lock to `UNLOCKED`.
     * 6. Snapshot-and-Verify: Confirms post-batch epoch strictly matches the pre-batch snapshot.
     */
    modifier guardBatchExecution() {
        if (isBatchExecuting()) {
            revert BatchReentrancyDetected();
        }

        // Step 1: Set transient lock
        _setBatchLock(LOCKED);

        // Step 2: Snapshot authority epoch
        AuthorityEpoch memory snapshot = _getAuthorityEpoch();
        emit BatchExecutionStarted(snapshot.epochCounter, snapshot.authorityHash);

        // Step 3: Execute external calls
        _;

        // Step 4: Clear transient lock
        _setBatchLock(UNLOCKED);

        // Step 5: Verify epoch invariance
        AuthorityEpoch memory current = _getAuthorityEpoch();
        if (
            current.epochCounter != snapshot.epochCounter ||
            current.authorityHash != snapshot.authorityHash
        ) {
            revert AuthorityEpochModified(
                snapshot.epochCounter,
                current.epochCounter,
                snapshot.authorityHash,
                current.authorityHash
            );
        }

        emit BatchExecutionCompleted(current.epochCounter, current.authorityHash);
    }

    /**
     * @notice Applied to all permissionless recovery transition functions:
     *         `finalizeRecovery()`, `confirmGuardianAddition()`, `confirmGuardianRevokation()`.
     *
     * MITIGATION LOGIC:
     * If an external contract called during `executeBatch()` attempts to invoke this function
     * via a reentrancy callback, `isBatchExecuting()` will return true. The transaction
     * immediately reverts with `AuthorityInFlux()`, halting the TOCTOU attack.
     */
    modifier disallowDuringBatch() {
        if (isBatchExecuting()) {
            revert AuthorityInFlux();
        }
        _;
    }

    // =========================================================================
    // AUTHORITY EPOCH LOGIC (CEI ENFORCED)
    // =========================================================================

    /// @notice Returns the current packed authority epoch.
    function _getAuthorityEpoch() internal view returns (AuthorityEpoch memory) {
        AuthorityGuardStorage storage $ = _getAuthorityGuardStorage();
        return $.epoch;
    }

    /// @notice Public view function for off-chain inspection and bundler simulation.
    function getAuthorityEpoch() external view returns (uint64 epochCounter, bytes32 authorityHash) {
        AuthorityEpoch memory ep = _getAuthorityEpoch();
        return (ep.epochCounter, ep.authorityHash);
    }

    /**
     * @notice Updates the authority epoch state.
     * @dev Strictly follows Checks-Effects-Interactions (CEI).
     *      Must be called by internal state-transition functions whenever
     *      the owner, guardians, or authorized modules change.
     * @param newAuthorityHash Keccak256 hash representing the newly finalized authority set.
     */
    function _updateAuthorityEpoch(bytes32 newAuthorityHash) internal {
        if (newAuthorityHash == bytes32(0)) {
            revert InvalidAuthorityHash();
        }

        AuthorityGuardStorage storage $ = _getAuthorityGuardStorage();

        unchecked {
            $.epoch.epochCounter += 1;
        }
        $.epoch.authorityHash = newAuthorityHash;

        emit AuthorityEpochUpdated($.epoch.epochCounter, newAuthorityHash);
    }

    /**
     * @notice Pure helper to compute authority hash from components.
     */
    function _computeAuthorityHash(
        address owner,
        address[] memory guardians,
        address[] memory modules
    ) internal pure returns (bytes32) {
        return keccak256(abi.encode(owner, guardians, modules));
    }
}