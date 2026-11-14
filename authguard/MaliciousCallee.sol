// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IRecoverable {
    function finalizeRecovery() external;
}

/**
 * @title MaliciousCallee
 * @dev Simulates an untrusted contract (e.g. an ERC-777 hook or malicious DeFi protocol)
 *      that re-enters `finalizeRecovery()` while the wallet is mid-batch.
 *      Reverts are NOT swallowed, so a guard revert propagates to the wallet.
 */
contract MaliciousCallee {
    IRecoverable public immutable target;
    bool public attackAttempted;
    bool public attackSucceeded;

    constructor(address _target) {
        target = IRecoverable(_target);
    }

    fallback() external payable {
        _attack();
    }

    receive() external payable {
        _attack();
    }

    function _attack() internal {
        attackAttempted = true;
        target.finalizeRecovery();
        attackSucceeded = true;
    }
}
