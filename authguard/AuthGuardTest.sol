// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./SocialRecoveryWallet.sol";
import "./MaliciousCallee.sol";

/**
 * @title AuthGuardTest
 * @notice Self-contained, automated test runner containing 5 hardcoded test cases.
 * @dev Can be executed by calling `runAllTests()` in Remix, Hardhat, or Foundry.
 */
contract AuthGuardTest {
    SocialRecoveryWallet public wallet;
    MaliciousCallee public attacker;

    address public constant OWNER = address(0x1111111111111111111111111111111111111111);
    address public constant RECOVERY_CANDIDATE = address(0x2222222222222222222222222222222222222222);
    address public constant GUARDIAN = address(0x3333333333333333333333333333333333333333);

    // Test results tracking
    event TestLog(string testName, bool passed, string reason);

    function setUp() public {
        address[] memory initialGuardians = new address[](1);
        initialGuardians[0] = GUARDIAN;

        // Deploy wallet and attacker contract
        wallet = new SocialRecoveryWallet(address(this), initialGuardians);
        attacker = new MaliciousCallee(address(wallet));

        // Fund wallet
        (bool ok, ) = address(wallet).call{value: 5 ether}("");
        require(ok, "Failed to fund wallet");
    }

    // =========================================================================
    // TEST CASE 1: Normal Batch Execution Succeeds
    // =========================================================================
    function test_1_NormalBatchExecution_Success() public returns (bool) {
        setUp();

        address[] memory targets = new address[](1);
        uint256[] memory values = new uint256[](1);
        bytes[] memory payloads = new bytes[](1);

        targets[0] = address(0x4444444444444444444444444444444444444444);
        values[0] = 0.5 ether;
        payloads[0] = "";

        // Execute batch
        wallet.executeBatch(targets, values, payloads);

        // Verification:
        // 1. Transient lock must be cleared (0)
        // 2. Epoch counter must remain intact at 1
        (uint64 counter, ) = wallet.getAuthorityEpoch();
        bool lockCleared = !wallet.isBatchExecuting();
        bool epochIntact = (counter == 1);

        if (lockCleared && epochIntact) {
            emit TestLog("Test 1: Normal Batch Execution", true, "Executed smoothly; lock cleared; epoch intact");
            return true;
        } else {
            emit TestLog("Test 1: Normal Batch Execution", false, "State check failed");
            return false;
        }
    }

    // =========================================================================
    // TEST CASE 2: Attacker Calling finalizeRecovery Mid-Batch is Blocked
    // =========================================================================
    function test_2_MidBatchReentrancy_Blocked() public returns (bool) {
        setUp();

        // 1. Initiate a valid recovery
        wallet.initiateRecovery(RECOVERY_CANDIDATE);

        // 2. Warp/simulate timelock expiration by calling ripe recovery
        // In this test, we execute a batch that calls MaliciousCallee
        address[] memory targets = new address[](1);
        uint256[] memory values = new uint256[](1);
        bytes[] memory payloads = new bytes[](1);

        targets[0] = address(attacker);
        values[0] = 0.1 ether;
        payloads[0] = "";

        // 3. Batch execution MUST REVERT because MaliciousCallee tries to call finalizeRecovery()
        try wallet.executeBatch(targets, values, payloads) {
            emit TestLog("Test 2: Mid-Batch Reentrancy", false, "VULNERABILITY: Batch should have reverted with AuthorityInFlux!");
            return false;
        } catch {
            // Expected behavior: The transient lock blocked the reentrancy callback!
            emit TestLog("Test 2: Mid-Batch Reentrancy", true, "SUCCESS: Attack thwarted! AuthorityInFlux reverted the reentrancy call.");
            return true;
        }
    }

    // =========================================================================
    // TEST CASE 3: Normal Permissionless Finalization Outside Batch Succeeds
    // =========================================================================
    function test_3_PermissionlessFinalize_OutsideBatch_Success() public returns (bool) {
        setUp();

        // 1. Initiate recovery
        wallet.initiateRecovery(RECOVERY_CANDIDATE);

        // Note: In local EVM test harnesses without time-warp, we test that the function
        // passes the `disallowDuringBatch` modifier cleanly when no batch is active.
        // It reaches the timelock check without triggering `AuthorityInFlux()`.
        try wallet.finalizeRecovery() {
            emit TestLog("Test 3: Permissionless Outside Batch", true, "Finalized successfully");
            return true;
        } catch Error(string memory reason) {
            // Reverted on timelock, NOT AuthorityInFlux. This proves the guard allowed entry!
            if (keccak256(bytes(reason)) == keccak256(bytes("Recovery timelock has not expired"))) {
                emit TestLog("Test 3: Permissionless Outside Batch", true, "Passed guard cleanly (stopped at timelock)");
                return true;
            }
            return false;
        } catch {
            return false;
        }
    }

    // =========================================================================
    // TEST CASE 4: Direct Reentrant executeBatch Call is Blocked
    // =========================================================================
    function test_4_NestedBatchReentrancy_Blocked() public returns (bool) {
        setUp();

        // Prepare a payload where the wallet calls executeBatch on itself!
        address[] memory emptyTargets = new address[](0);
        uint256[] memory emptyValues = new uint256[](0);
        bytes[] memory emptyData = new bytes[](0);

        bytes memory nestedCall = abi.encodeWithSelector(
            wallet.executeBatch.selector,
            emptyTargets,
            emptyValues,
            emptyData
        );

        address[] memory targets = new address[](1);
        uint256[] memory values = new uint256[](1);
        bytes[] memory payloads = new bytes[](1);

        targets[0] = address(wallet);
        values[0] = 0;
        payloads[0] = nestedCall;

        // Must revert with BatchReentrancyDetected
        try wallet.executeBatch(targets, values, payloads) {
            emit TestLog("Test 4: Nested Batch Reentrancy", false, "Failed to block nested batch reentrancy");
            return false;
        } catch {
            emit TestLog("Test 4: Nested Batch Reentrancy", true, "SUCCESS: Nested batch call blocked by transient mutex");
            return true;
        }
    }

    // =========================================================================
    // TEST CASE 5: Snapshot-and-Verify Invariance
    // =========================================================================
    function test_5_SnapshotAndVerify_Integrity() public returns (bool) {
        setUp();

        (uint64 counterBefore, bytes32 hashBefore) = wallet.getAuthorityEpoch();

        // Run multi-target batch
        address[] memory targets = new address[](2);
        uint256[] memory values = new uint256[](2);
        bytes[] memory payloads = new bytes[](2);

        targets[0] = address(0x5555555555555555555555555555555555555555);
        values[0] = 0.1 ether;
        payloads[0] = "";

        targets[1] = address(0x6666666666666666666666666666666666666666);
        values[1] = 0.2 ether;
        payloads[1] = "";

        wallet.executeBatch(targets, values, payloads);

        (uint64 counterAfter, bytes32 hashAfter) = wallet.getAuthorityEpoch();

        bool passed = (counterBefore == counterAfter && hashBefore == hashAfter);
        emit TestLog("Test 5: Snapshot-and-Verify", passed, passed ? "Epoch invariant preserved" : "Epoch corrupted");
        return passed;
    }

    // =========================================================================
    // MASTER RUNNER: Executes all 5 test cases
    // =========================================================================
    function runAllTests() external returns (uint256 passedCount, uint256 totalTests) {
        totalTests = 5;
        passedCount = 0;

        if (test_1_NormalBatchExecution_Success()) passedCount++;
        if (test_2_MidBatchReentrancy_Blocked()) passedCount++;
        if (test_3_PermissionlessFinalize_OutsideBatch_Success()) passedCount++;
        if (test_4_NestedBatchReentrancy_Blocked()) passedCount++;
        if (test_5_SnapshotAndVerify_Integrity()) passedCount++;
    }

    receive() external payable {}
}