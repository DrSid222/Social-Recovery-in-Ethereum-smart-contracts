// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "./SocialRecoveryWallet.sol";
import "./MaliciousCallee.sol";

/// @dev Control: same recovery logic WITHOUT AuthorityGuard. The attack must succeed here.
contract UnguardedWallet {
    address public owner;
    address public pendingNewOwner;
    bool public ready;

    constructor(address o) { owner = o; }

    function arm(address n) external { pendingNewOwner = n; ready = true; } // test-only: recovery already finalizable

    function finalizeRecovery() external {
        require(ready, "none");
        owner = pendingNewOwner;
        ready = false;
    }

    function executeBatch(address[] calldata t, uint256[] calldata v, bytes[] calldata d) external payable {
        require(msg.sender == owner, "owner");
        for (uint256 i = 0; i < t.length; i++) {
            (bool ok, ) = t[i].call{value: v[i]}(d[i]);
            require(ok, "call");
        }
    }

    receive() external payable {}
}

/// @dev Smart-contract owner, so a batch callee can legitimately re-enter executeBatch.
contract ReentrantOwner {
    SocialRecoveryWallet public w;
    function setWallet(address a) external { w = SocialRecoveryWallet(payable(a)); }
    function run(address[] calldata t, uint256[] calldata v, bytes[] calldata d) external { w.executeBatch(t, v, d); }
    function hook() external { w.executeBatch(new address[](0), new uint256[](0), new bytes[](0)); }
}

/// @dev Harness that (wrongly) mutates authority inside a guarded batch -> snapshot-and-verify must catch it.
contract DriftHarness is AuthorityGuard {
    function run() external guardBatchExecution {
        _updateAuthorityEpoch(keccak256("drift"));
    }
}

contract AuthGuardTest is Test {
    SocialRecoveryWallet wallet;
    MaliciousCallee attacker;

    address owner = makeAddr("owner");
    address g1 = makeAddr("g1");
    address g2 = makeAddr("g2");
    address g3 = makeAddr("g3");
    address candidate = makeAddr("candidate");
    address outsider = makeAddr("outsider");
    address payee = makeAddr("payee");

    function setUp() public {
        address[] memory gs = new address[](3);
        gs[0] = g1; gs[1] = g2; gs[2] = g3;
        wallet = new SocialRecoveryWallet(owner, gs, 2);
        vm.deal(address(wallet), 5 ether);
        attacker = new MaliciousCallee(address(wallet));
    }

    // ---- helpers ----
    function _one(address t, uint256 v, bytes memory d)
        internal pure returns (address[] memory ts, uint256[] memory vs, bytes[] memory ds)
    {
        ts = new address[](1); vs = new uint256[](1); ds = new bytes[](1);
        ts[0] = t; vs[0] = v; ds[0] = d;
    }

    function _readyRecovery() internal {
        vm.prank(g1); wallet.initiateRecovery(candidate);
        vm.prank(g2); wallet.supportRecovery();
        vm.warp(block.timestamp + 24 hours);
    }

    // 1. normal batch succeeds, lock cleared, epoch unchanged
    function test_NormalBatchExecution() public {
        (address[] memory t, uint256[] memory v, bytes[] memory d) = _one(payee, 0.5 ether, "");
        vm.prank(owner);
        wallet.executeBatch(t, v, d);

        (uint64 counter, ) = wallet.getAuthorityEpoch();
        assertEq(payee.balance, 0.5 ether);
        assertFalse(wallet.isBatchExecuting());
        assertEq(counter, 1);
    }

    // 2. reentrant finalizeRecovery mid-batch is blocked, on a recovery that WOULD be finalizable
    function test_MidBatchReentrancy_Blocked() public {
        _readyRecovery();
        (address[] memory t, uint256[] memory v, bytes[] memory d) = _one(address(attacker), 0.1 ether, "");

        vm.prank(owner);
        vm.expectRevert(AuthorityGuard.AuthorityInFlux.selector);
        wallet.executeBatch(t, v, d);

        assertEq(wallet.owner(), owner);
        assertTrue(wallet.isRecoveryPending());
    }

    // 3. CONTROL: same attack on an unguarded wallet succeeds -> test 2 is meaningful
    function test_Control_UnguardedWallet_IsVulnerable() public {
        UnguardedWallet bad = new UnguardedWallet(owner);
        vm.deal(address(bad), 5 ether);
        bad.arm(candidate);
        MaliciousCallee atk = new MaliciousCallee(address(bad));

        (address[] memory t, uint256[] memory v, bytes[] memory d) = _one(address(atk), 0.1 ether, "");
        vm.prank(owner);
        bad.executeBatch(t, v, d);

        assertTrue(atk.attackSucceeded());
        assertEq(bad.owner(), candidate); // authority changed mid-batch
    }

    // 4. permissionless finalize outside a batch works after timelock + threshold
    function test_PermissionlessFinalize_OutsideBatch() public {
        _readyRecovery();
        (, bytes32 hashBefore) = wallet.getAuthorityEpoch();

        vm.prank(outsider);
        wallet.finalizeRecovery();

        (uint64 counter, bytes32 hashAfter) = wallet.getAuthorityEpoch();
        assertEq(wallet.owner(), candidate);
        assertFalse(wallet.isRecoveryPending());
        assertEq(counter, 2);
        assertTrue(hashAfter != hashBefore);
    }

    // 5. finalize rejected before timelock / below threshold
    function test_Finalize_RevertsBeforeTimelock() public {
        vm.prank(g1); wallet.initiateRecovery(candidate);
        vm.prank(g2); wallet.supportRecovery();
        vm.expectRevert(SocialRecoveryWallet.TimelockNotExpired.selector);
        wallet.finalizeRecovery();
    }

    function test_Finalize_RevertsBelowThreshold() public {
        vm.prank(g1); wallet.initiateRecovery(candidate);
        vm.warp(block.timestamp + 24 hours);
        vm.expectRevert(SocialRecoveryWallet.ThresholdNotMet.selector);
        wallet.finalizeRecovery();
    }

    // 6. nested executeBatch by a contract owner is blocked by the mutex
    function test_NestedBatchReentrancy_Blocked() public {
        ReentrantOwner ro = new ReentrantOwner();
        address[] memory gs = new address[](1);
        gs[0] = g1;
        SocialRecoveryWallet w2 = new SocialRecoveryWallet(address(ro), gs, 1);
        ro.setWallet(address(w2));

        (address[] memory t, uint256[] memory v, bytes[] memory d) =
            _one(address(ro), 0, abi.encodeCall(ReentrantOwner.hook, ()));

        vm.expectRevert(AuthorityGuard.BatchReentrancyDetected.selector);
        ro.run(t, v, d);
    }

    // 7. snapshot-and-verify catches authority drift inside a guarded batch
    function test_SnapshotAndVerify_DetectsDrift() public {
        DriftHarness h = new DriftHarness();
        vm.expectRevert(
            abi.encodeWithSelector(
                AuthorityGuard.AuthorityEpochModified.selector, uint64(0), uint64(1), bytes32(0), keccak256("drift")
            )
        );
        h.run();
    }

    // 8. access control
    function test_NonGuardianCannotInitiate() public {
        vm.prank(outsider);
        vm.expectRevert(SocialRecoveryWallet.NotGuardian.selector);
        wallet.initiateRecovery(candidate);
    }

    function test_OwnerCanCancel_NonOwnerCannot() public {
        vm.prank(g1); wallet.initiateRecovery(candidate);

        vm.prank(outsider);
        vm.expectRevert(SocialRecoveryWallet.NotOwner.selector);
        wallet.cancelRecovery();

        vm.prank(owner);
        wallet.cancelRecovery();
        assertFalse(wallet.isRecoveryPending());
    }

    function test_DoubleSupportReverts() public {
        vm.prank(g1); wallet.initiateRecovery(candidate);
        vm.prank(g1);
        vm.expectRevert(SocialRecoveryWallet.AlreadySupported.selector);
        wallet.supportRecovery();
    }
}
