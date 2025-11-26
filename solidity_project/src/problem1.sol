// SPDX-License-Identifier: MIT

// Means 0.8.0 or later version of Solidity
pragma solidity ^0.8.0;

// Import OpenZeppelin's ERC1155 from the GitHub
// It will be fail if no internet access
// Or in the progress of testing
// so better to install the OpenZeppelin Contracts library
// forge install OpenZeppelin/openzeppelin-contracts
// import "https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/ERC20.sol";
import { ERC20 } from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/*
1. According to the Requirement,
There should be only 1 manufacturer, 1 distributor, and 1 retailer.

Because address only store 1 people's address,
not address[]

2. According to the requirement,
We do not care about the product details and multiple products.
Because getHistory not requires any input parameters.
If there are multiple products,
ProductID should be offered for specific product.
AND updateStatus has only 1 input parameter, newStatus.
It does not have ProductID input parameter.

So we assume there is only 1 product in the supply chain.
And we do not care about the product details.



 */
contract SupplyChainTracking is ERC20 {
    // Role-Based Updates:
    enum Role {
        Manufacturer,
        Distributor,
        Retailer,
        UnAuthorized
    }

    // Declare the variables
    address private immutable MANUFACTURER_ADDRESS;
    address private immutable DISTRIBUTOR_ADDRESS;
    address private immutable RETAILER_ADDRESS;

    // Store the 1 coin/token, not the minimum unit
    // e.g., 1 token = 10^18 minimum unit (wei)
    // decimals() is an internal function in ERC20
    // It returns the number of decimals of the minimum unit
    // it returns uint8
    // So we need to convert it to uint256
    // should not be changed be user easily, else they can change the coin easily
    uint256 private immutable EACH_FULL_COIN = 10 ** uint256(decimals());

    // Immutable History: 
    // Only appendable in the following functions
    // history of the product status updates
    // Nobody can access/change the history directly
    // default and MUST to be storage
    // auto-init to [], not allowed to assign []
    string[] private  __history;
    
    // Required Constructor 1
    constructor(address manufacturer, address distributor, address retailer) 
        ERC20(
            // Coin name
            "SupplyChainCoin",
            // Coin symbol, e.g.,  "SCC" for "Supply Chain Coin"
            "SCC"
            ) {
        MANUFACTURER_ADDRESS = manufacturer;
        DISTRIBUTOR_ADDRESS = distributor;
        RETAILER_ADDRESS = retailer;
    }

    // Getter for EACH_FULL_COIN
    function getEachFullCoin() 
    public view returns (uint256) {
        return EACH_FULL_COIN;
    }


    // Getter functions for the addresses
    function getManufacturerAddress()
    public view returns (address) {
        return MANUFACTURER_ADDRESS;
    }



    function getDistributorAddress()
    public view returns (address) {
        return DISTRIBUTOR_ADDRESS;
    }

    function getRetailerAddress()
    public view returns (address) {
        return RETAILER_ADDRESS;
    }

    // Role-Based Updates:
    // view: not change the blockchain state
    // internal: same as "protected"
    function _checkRole(address user)
    internal view returns (Role) {
        // Check Role By Role: According to the Address
        if (user == MANUFACTURER_ADDRESS) {
            return Role.Manufacturer;
        } else if (user == DISTRIBUTOR_ADDRESS) {
            return Role.Distributor;
        } else if (user == RETAILER_ADDRESS) {
            return Role.Retailer;

        // Else: Invalid Role
        } else { 
            return Role.UnAuthorized;
        }
    }

    // Event Emission:
    event eventTryingToUpdateStatus(address indexed user, string indexed newStatus);

    // Required Function 2
    function updateStatus (string memory newStatus)
    public {
        // Event Emission:
        // Each update should trigger an on-chain event
        // (Actually, all events are stored in the blockchain (on-chain event log))
        emit eventTryingToUpdateStatus(msg.sender, newStatus);
        
        // Role-Based Updates:
        // Check && Get the Role of the Caller
        Role userRole = _checkRole(msg.sender);

        // why require instead of revert?
        // Require will revert the transaction if the condition is not met
        // It add the error message
        // It will not consume gas if the condition is met
        // It rollback the state changes if the condition is not met
        // Its logic is simple
        // Check the Role
        require(userRole != Role.UnAuthorized, "Unauthorized: Unauthorized user");

        // Immutable History: 
        // Else: Authorized User
        // Update the History
        __history.push(newStatus);


        // Reward Mechanism: 
        // Successful Update
        // Reward the Caller with 1 token/coin
        // _mint is an internal function in ERC20
        // It creates `amount` token/coin and assigns them to `account`, 
        // increasing the total supply/ create new token/coin
        // we do not use mapping(address => uint256) public balanceOf;
        // ERC20 is easier to use
        // just do _mint and balanceOf(address) 
        // there is no mint function in ERC20
        // prefix "_" for internal functions
        _mint(msg.sender, EACH_FULL_COIN);

    } 

    // Transparency and Access: 
    // Required Function 3
    function getHistory()
    public view returns (string[] memory) {
        return __history;
    }
    // No set history


    // Transparency and Access: 
    // Required Function 4
    function getRewardBalance(address participant) 
    public view returns (uint256) {
        // not mapping(address => uint256) public balanceOf;
        // so not use balanceOf[participant];
        // use balanceOf(address) in ERC20
        return balanceOf(participant);
    }

}
