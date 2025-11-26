// SPDX-License-Identifier: MIT

// Means 0.8.0 or later version of Solidity
pragma solidity ^0.8.0;

contract ThreePartyEscrowSmartContract {

    address private immutable BUYER;
    address private immutable SELLER;
    address private immutable MEDIATOR;

    struct ActionGroup {
        bool hasApproved;
    }

    struct ActionCount {
        uint256 totalApprovedCount;
    }

    // check for approvals, no repeat approvals
    struct PartyGroup {
        ActionGroup buyerAction;
        ActionGroup sellerAction;
        ActionGroup mediatorAction;
        ActionCount actionCount;
    }

    PartyGroup private allPartyActions;
    // Payment records
    bool private buyerDeposited;
    mapping(address => uint256) private depositRecords;


    enum Role {
        Buyer,
        Seller,
        Mediator,
        UnAuthorized
    }

    // Escrow status
    enum EscrowStatus {
        Pending,
        Approved,
        FundsReleased
    }

    EscrowStatus private escrowStatus;

    // Event Tracking: Contract emits approval and release events for external auditing.
    // indexed for filtering, at most 3 indexed parameters allowed
    event DepositEvent(address indexed buyer, uint256 amount);
    event ApproveEvent(address indexed approver, string role);
    event FundsReleasedEvent(address indexed seller, uint256 amount);



    constructor(
        address buyer,
        address seller,
        address mediator
    ) {
        BUYER = buyer;
        SELLER = seller;
        MEDIATOR = mediator;
        escrowStatus = EscrowStatus.Pending;
    }
    
    
    function _getRole(address user) internal view returns (Role) {
        if (user == BUYER) {
            return Role.Buyer;
        } else if (user == SELLER) {
            return Role.Seller;
        } else if (user == MEDIATOR) {
            return Role.Mediator;
        } else {
            return Role.UnAuthorized;
        }
    }

    

    // Secure Deposit:  Buyer sends Ether to the contract to lock funds on-chain
    function deposit() payable public {
        // make sure that only buyer can deposit funds
        require(
            msg.sender == BUYER,
            "Unauthorized: Only buyer can deposit funds"
        );

        require(
            escrowStatus == EscrowStatus.Pending,
            "Escrow is not in pending status"
        );
        // Fail-Safe Design:  Prevents "double-payouts" or re-approvals by the same party.
        // Make sure only one deposit
        // the buyerDeposited is false at the beginning
        require(
            !buyerDeposited,
            "Deposit has already been made"
        );
        
        // if the buyer does not have enough ether,
        // the transaction will fail automatically
        // no need to check the balance here

        // Since the buyer does not offer the number of money,
        // we cannot check the amount here is right or wrong
        // The interface should exactly same to the offered with no amount parameter
        // We trust the buyer to deposit the right amount of money
        // So, no require(msg.value == amount, "Deposit amount mismatch");
        

        // record the deposit amount
        // lock the funds in the contract
        // The Buyer put the money in the contract, not the seller.
        // the money have been sent to the seller
        // the record might be zero; amount is also 0
        // Double check of the deposit amount
        // Fail-Safe Design:  Prevents double-payouts or re-approvals by the same party.
        depositRecords[BUYER] += msg.value;

        // Set the deposit flag to true
        // the buyer has deposited the money
        buyerDeposited = true;

        // finish deposit
        // emit event
        emit DepositEvent(msg.sender, msg.value);
    }

    function _returnStringFromEnumRole(Role role) internal pure returns (string memory) {
        if (role == Role.Buyer) {
            return "Buyer";
        } else if (role == Role.Seller) {
            return "Seller";
        } else if (role == Role.Mediator) {
            return "Mediator";
        } else {
            return "UnAuthorized";
        }
    }

    // Approval
    function approveRelease() public {
        Role userRole = _getRole(msg.sender);
        // make sure not other people besides the three parties 
        require(
            userRole != Role.UnAuthorized,
            "Unauthorized: Unauthorized user"
        );

        // check No.1
        // make sure the money is already deposited
        require(
            buyerDeposited,
            "No funds deposited yet; cannot approve release"
        );

        // Approval Logic: Buyer, seller, or mediator may call approveRelease;
        // Fail-Safe Design: Prevents double-payouts or "re-approvals" by the same party.
        // each only once
        // check if already approved
        if (userRole == Role.Buyer) {
            require(
                !allPartyActions.buyerAction.hasApproved,
                "Buyer has already approved"
            );
            allPartyActions.buyerAction = ActionGroup({ hasApproved: true });
        } else if (userRole == Role.Seller) {
            require(
                !allPartyActions.sellerAction.hasApproved,
                "Seller has already approved"
            );
            allPartyActions.sellerAction = ActionGroup({ hasApproved: true });
        } else if (userRole == Role.Mediator) {
            require(
                !allPartyActions.mediatorAction.hasApproved,
                "Mediator has already approved"
            );
            allPartyActions.mediatorAction = ActionGroup({ hasApproved: true });
        } else {
            // This is impossible since already checked above
            revert("require(userRole != Role.UnAuthorized) failed; reach this impossible branch");
        }

        // Approved finish, emit event
        emit ApproveEvent(
            msg.sender, 
            // Impossible to be UnAuthorized here
            // It has been checked above
            _returnStringFromEnumRole(userRole)
        );

        // increment approval count
        allPartyActions.actionCount.totalApprovedCount += 1;

        if (allPartyActions.actionCount.totalApprovedCount == 1) {
            // not doing things

            // First Approval:  On the first approval, 
            // it is  not fully approved yet
        }
        // Check if all parties have approved
        // Consensus Release:  If ≥ 2 approvals are detected,
        // Ether releases to the seller.
        else if (allPartyActions.actionCount.totalApprovedCount >= 2) {
            // Fail-Safe Design:  Prevents double-payouts or re-approvals by the same party.
            // Check released?
            // release only once
            // check No.2
            // if not released yet
            if (escrowStatus != EscrowStatus.FundsReleased) {
                // update status to Approved
                escrowStatus = EscrowStatus.Approved;
                // release the funds to the seller and do operations
                finalizeRelease();
                // when finish release, update status, this ensure the real release, is the real status.
                escrowStatus = EscrowStatus.FundsReleased;

            // if already released
            } else {
                // Here does not need to revert, we have the check above
                // revert("Funds have already been released");
                // Here is the condition that: allPartyActions.actionCount.totalApprovedCount > half
                // Do not do anything.
            }
        } else {
            // This is impossible since min = 0
            // already plused 1 above
            revert("Invalid approval count 0, fail to add allPartyActions.actionCount.totalApprovedCount; reach this impossible branch");
        }
    }

    function finalizeRelease() internal {
        // transfer the funds to the seller
        // this could only be called by approveRelease function

        uint256 buyerDepositedAmount = depositRecords[BUYER];

        // check No.2
        // Fail-Safe Design:  Prevents double-payouts or re-approvals by the same party.
        // check Whether the funds have been released Approved Now!
        // double check
        if (escrowStatus == EscrowStatus.FundsReleased) {
            revert("Funds have already been released");
        } else if (escrowStatus == EscrowStatus.Pending) {
            // never reach here in current logic
            revert("Escrow is in pending status, cannot release funds");
        } else {
            // else escrowStatus == EscrowStatus.Approved
            // go next
        }

        // Check the deposit again
        // we only have one buyer and contract on this solidity contract
        require(buyerDepositedAmount == address(this).balance,
            "Deposit amount mismatch"
        );


        // check No.1
        // Fail-Safe Design:  Prevents double-payouts or re-approvals by the same party.
        // check the freeze money is true
        // Double check; Although already checked in approveRelease
        // Allow 0-value deposits
        require(
            buyerDeposited,
            "No funds deposited to release; cannot release funds"
        );

        // transfer the funds to the seller
        payable(SELLER).transfer(buyerDepositedAmount);
        // finish the release
        emit FundsReleasedEvent(SELLER, buyerDepositedAmount);

        // Clear the record of deposit
        depositRecords[BUYER] = 0;

        // Finally, update the escrow status
        escrowStatus = EscrowStatus.FundsReleased;

        // Remember not to reset the approval records
        // to prevent re-approval and double-payouts

        // And we need getter functions to check the status
    }

    function getEscrowStatus() public view returns (string memory) {
        if (escrowStatus == EscrowStatus.Pending) {
            return "Pending";
        } else if (escrowStatus == EscrowStatus.Approved) {
            return "Approved";
        } else if (escrowStatus == EscrowStatus.FundsReleased) {
            return "Funds Released";
        } else {
            revert("Invalid escrow status, escrowStatus/EscrowStatus enum might be changed");
        }
    }
}