// SPDX-License-Identifier: MIT

pragma solidity ^0.8.0;


// Since the 
import { ERC20 } from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
// import { console } from "forge-std/console.sol";

contract DecentralizedTreasuryManagement is ERC20 {

    // Address or identifier for the DAO treasury
    address private immutable DAO_TREASURY;

    // Address of the deployer or admin
    // Not strictly necessary for this question
    address private immutable CONTRACT_DEPLOYER;

    // Member Management
    address[] private members;
    mapping(address => bool) private isMember;

    // Proposal Structure
    struct Proposal {
        uint256 id;
        address payable to;
        uint256 amount;
        string description;
        // Vote counts
        uint256 yesVotes;
        uint256 noVotes;
        // Stop if executed
        bool executed;
        // prevent double voting
        mapping(address => bool) voters;
        // mapping is not iterable, so we use array to store the voter list if needed
        address[] voterList;
    }

    // Proposals mapping
    mapping(uint256 => Proposal) private proposals;
    // Counter increasing
    uint256 private proposalCount;

    // Voting Process:  Members vote with power proportional to their token holdings.
    mapping(address => uint256) private votingPower;

    // Total voting power
    uint256 private totalVotingPower;

    // Initializes the DAO treasury 
    // and assigns initial voting power to the deployer or token holders.
    constructor() 
    ERC20("DecentralizedTreasuryToken", "DTT")
    {
        // Record the deployer
        CONTRACT_DEPLOYER = msg.sender;
        
        // Init the DAO treasury
        DAO_TREASURY = address(this);

        // assign the initial voting power to the deployer or token holders
        // According to the token holdings
        // since there is no token implemented yet
        // the default value is 0,
        // it will cause a Divide-by-zero error when voting
        // Therefore, we can assign a default voting power to the deployer
        // To convenient the voting
        uint256 initVotingPower = 1 gwei;
        votingPower[msg.sender] = initVotingPower;
        // Add to total Voting Power
        totalVotingPower += initVotingPower;

        // Mark as member
        isMember[msg.sender] = true;
        members.push(msg.sender);
    }

    // ------------------- Getters -------------------
    function getVotingPower(address member) 
    view 
    public
    returns (uint256) {
        return votingPower[member];
    }

    // ------------------- Guards and Modifiers -------------------


    function _checkMemberVotedFunction(Proposal storage proposal)
    view 
    internal {
        require(
            !proposal.voters[msg.sender],
            "Member has already voted on this proposal"
        );
    }

    function _checkMemberVotedFunction(uint256 proposalId)
    view 
    internal {
        Proposal storage proposal = proposals[proposalId];
        _checkMemberVotedFunction(proposal);
    }

    function _checkProposalIsOpenFunction(Proposal storage proposal) 
    view 
    internal {
        require(
            !proposal.executed,
            "Proposal is already executed/closed"
        );
    }

    function _checkProposalIsOpenFunction(uint256 proposalId) 
    view 
    internal {
        Proposal storage proposal = proposals[proposalId];
        _checkProposalIsOpenFunction(proposal);
    }

    function _requireMember() internal view {
        require(
            isMember[msg.sender] == true,
            "Only member can perform this action"
        );
    }

    // Corresponding Modifiers
    modifier requireMemberNotVoted(uint256 proposalId) {
        _checkMemberVotedFunction(proposalId);
        // Occupier of the other function
        _;
    }

    modifier requireProposalIsOpen(uint256 proposalId) {
        _checkProposalIsOpenFunction(proposalId);
        // Occupier of the other function
        _;
    }
    
    modifier onlyMember() {
        _requireMember();
        // Occupier of the other function
        _;
    }

    // ------------------- Proposal Vote Success/Fail Trigger Functions -------------------
    // only view/read the proposal, prefer memory
    // But there is mapping in the struct, so we cannot use memory
    // Use storage
    function checkProposalMeetThresholds(Proposal storage proposal)
    view 
    internal  
    returns (uint256) 
    {
        // Execution Rules: Transfers are auto-executed once affirmative votes exceed 50% of total voting power.
        // Define thresholds
        uint256 approvalThreshold = (totalVotingPower * 50) / 100; // 50% approval
        uint256 rejectionThreshold = (totalVotingPower * 50) / 100;   // 50% rejection

        // Check if proposal meets thresholds
        if (proposal.yesVotes > approvalThreshold) {
            return 1;
        } else if (proposal.noVotes > rejectionThreshold) {
            return 2;
        } else {
            return 0;
        }
    }

    // overloaded function
    function checkProposalMeetThresholds(uint256 proposalId)
    view 
    internal 
    returns (uint256) 
    {
        Proposal storage proposal = proposals[proposalId];

        return checkProposalMeetThresholds(proposal);
    }

    // ------------------- Events -------------------
        // Proposal Lifecycle Logging:  Key actions emit events for external indexing.
    event ProposalCreated(uint256 indexed proposalId, address indexed proposer, address to, uint256 amount, string description);
    event VoteCast(address indexed voter, uint256 indexed proposalId, bool support, uint256 votingPower);
    event ProposalExecuted(uint256 indexed proposalId, address to, uint256 amount);

    event TreasuryBalanceReceived(address donator, uint256 amount);

    // Non standard Event for testing
    event AddMember(address member, uint256 initialVotingPower);

    // checking the balance of the treasury is not necessary
    // so no event for get basic treasury info


    // ------------------- Core Functions -------------------
    // Creates a proposal specifying the recipient, amount, and purpose.
    // Proposal Creation:  Any member can propose a payment or funding allocation.
    // Public No limits No Requirement No Modifier
    function proposeTransfer(address to, uint256 amount, string memory description)
    onlyMember()
    public {
        // requier amount cannot be 0 or exceed treasury balance
        require(
            amount > 0,
            "Proposal amount must be greater than zero"
        );
        require(
            amount <= address(this).balance,
            "Proposal amount exceeds treasury balance"
        );

        // Create a new proposal
        // storage because we want to keep tracking the proposal
        Proposal storage newProposal = proposals[proposalCount];
        // Initialize proposal details
        newProposal.id = proposalCount;
        newProposal.to = payable(to);
        newProposal.amount = amount;
        newProposal.description = description;
        newProposal.yesVotes = 0;
        newProposal.noVotes = 0;
        newProposal.executed = false;

        // Increment proposal count
        proposalCount++;
        
        // Proposal Lifecycle Logging:  Key actions emit events for external indexing.
        // Emit event
        emit ProposalCreated(
            newProposal.id,
            msg.sender,
            newProposal.to,
            newProposal.amount,
            newProposal.description
        );
    }

    // Records a vote; adds to yesVotes if support= true, else noVotes.
    // Defaultly not allow double voting or Vote changing
    function vote(uint256 proposalId, bool support) 
    // Require the member has sufficient voting power
    onlyMember()
    public {
        Proposal storage proposal = proposals[proposalId];
        // Check if proposal is still open & member has not voted
        _checkProposalIsOpenFunction(proposal);
        _checkMemberVotedFunction(proposal);

        // Voting Process:  Members vote with power proportional to their token holdings.
        // Record the vote
        // support: true -> yesVotes
        // support: false -> noVotes
        uint256 voterPower = getVotingPower(msg.sender);
        if (support) {
            proposal.yesVotes += voterPower;
        } else {
            proposal.noVotes += voterPower;
        }

        // Mark the voter as having voted
        proposal.voters[msg.sender] = true;
        proposal.voterList.push(msg.sender);

        // Proposal Lifecycle Logging:  Key actions emit events for external indexing.
        // Emit event
        emit VoteCast(msg.sender, proposalId, support, voterPower);

        // ------------------- Check whether Execute Immediately -------------------
        // Immediately execute if thresholds are met
        uint256 thresholdResult = checkProposalMeetThresholds(proposal);

        if (thresholdResult == 1) {
            executeTransfer(proposal);
            // Mark as executed
            proposal.executed = true;
        } else if (thresholdResult == 2) {
            // Proposal rejected, no action needed
            proposal.executed = true;
            return;
        } else if (thresholdResult == 0) {
            // Thresholds not met, do nothing
            return;
        } else {
            // Should not reach here
            revert("Unexpected error in function checkProposalMeetThresholds");
        }
    }


    // overload a direct proposal, instead finding it by id again if already have it
    function executeTransfer(Proposal storage proposal)
    internal {
        // Check if already executed
        _checkProposalIsOpenFunction(proposal);

        // Transfer funds from DAO treasury to the specified address
        // NOT USE transfer function of ERC20 IT limits to 2300 gas
        (bool success, ) = proposal.to.call{value: proposal.amount}("");
        require(success, "Transfer failed");

        // not put the mark executed, it is not the work of this function

        // Proposal Lifecycle Logging:  Key actions emit events for external indexing.
        // Emit event
        emit ProposalExecuted(proposal.id, proposal.to, proposal.amount);
    }

    // Transfers requested funds to the proposal’s to address if it passes thresholds.
    function executeTransfer(uint256 proposalId)
    internal {
        Proposal storage proposal = proposals[proposalId];

        executeTransfer(proposal);
    }

    // Returns stored proposal details for display and monitoring.
    function getProposal(uint256 proposalId)
    public view returns (
        address to,
        uint256 amount,
        string memory description,
        uint256 yesVotes,
        uint256 noVotes,
        bool executed,
        address[] memory voterList
    ) {
        // mapping cannot be returned directly
        // so we return the voterList array instead
        Proposal storage proposal = proposals[proposalId];
        return (
            proposal.to,
            proposal.amount,
            proposal.description,
            proposal.yesVotes,
            proposal.noVotes,
            proposal.executed,
            proposal.voterList
        );
    }

    // Treasury Funding: Contract can receive Ether from DAO contributions and execute payouts.
    // Accept Ether deposits to the DAO treasury
    receive() 
    external 
    payable {
        // the ETH will auto-check the balance is sufficient or not
        // The accept Ether operation do not need to modify t(dtm).call{value: depositAmounhe balance
        // .value is a read-only property
        // So no need to do anything here
        
        // Proposal Lifecycle Logging:  Key actions emit events for external indexing.
        // Trigger event
        emit TreasuryBalanceReceived(msg.sender, msg.value);
    }

    // Fallback function to accept Ether
    fallback() 
    external 
    payable {
        // the ETH will auto-check the balance is sufficient or not
        // The accept Ether operation do not need to modify the balance
        // .value is a read-only property
        // So no need to do anything here

        // Proposal Lifecycle Logging:  Key actions emit events for external indexing.
        // Trigger event
        emit TreasuryBalanceReceived(msg.sender, msg.value);
    }

    // ------------------- Additional Functions (Not required in this Question) -------------------
    function getProposalCount()
    public view returns (uint256) {
        return proposalCount;
    }

    function getTotalVotingPower()
    public view returns (uint256) {
        return totalVotingPower;
    }

    // ------------ Member Adding (Not required in this Question) ------------------
    function _checkIsDeployer() view internal {
        require(
            msg.sender == CONTRACT_DEPLOYER, 
            "Only deployer can perform this action"
        );
    }
    
    modifier onlyDeployer() {
        _checkIsDeployer();
        // Occupier of the other function
        _;
    }

    function addMember(address newMember, uint256 initialVotingPower) public onlyDeployer {
        votingPower[newMember] = initialVotingPower;
        totalVotingPower += initialVotingPower;

        // Mark as member
        isMember[newMember] = true;
        members.push(newMember);

        emit AddMember(newMember, initialVotingPower);
    }

}