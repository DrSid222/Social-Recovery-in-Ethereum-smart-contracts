// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ISocialRecoveryWallet {
    function finalizeRecovery() external;
    function executeBatch(address[] calldata targets, uint256[] calldata values, bytes[] calldata data) external payable;
}

/**
 * @title MaliciousCallee
 * @dev Simulates an untrusted contract (e.g. an ERC-777 hook or malicious DeFi protocol)
 *      that attempts to hijack authority while the wallet is mid-batch.
 */
contract MaliciousCallee {
    ISocialRecoveryWallet public targetWallet;
    bool public attackAttempted;
    bool public attackSucceeded;

    constructor(address _targetWallet) {
        targetWallet = ISocialRecoveryWallet(_targetWallet);
    }

    /**
     * @dev Fallback hook triggered when the wallet calls this contract during `executeBatch()`.
     *      It immediately re-enters the wallet to execute `finalizeRecovery()`.
     */
    fallback() external payable {
        attackAttempted = true;
        // Attempt Authority Reentrancy exploit:
        targetWallet.finalizeRecovery();
        attackSucceeded = true;
    }

    receive() external payable {
        attackAttempted = true;
        targetWallet.finalizeRecovery();
        attackSucceeded = true;
    }
}