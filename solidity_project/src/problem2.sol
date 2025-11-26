// SPDX-License-Identifier: MIT

// Means 0.8.0 or later version of Solidity
pragma solidity ^0.8.0;


// Since the RenewableEnergyCredits is same to each other,
// other people can buy/sell/trade/use them,
// Therefore, we use ERC20 standard
// Import OpenZeppelin's ERC20 from the GitHub

import { ERC20 } from "@openzeppelin/contracts/token/ERC20/ERC20.sol";


/*
1.
According to the Requirement:
∴ There is only 1 contract owner/admin.
Explaination:
∵ It automatically set the deployer as the contract owner.
∵ There is only 1 deployer.
2.
∵ we have registerProducer() function
∴ There can be multiple producers.
Explaination:
∵ The function allows adding new producers to the system.
∵ Each producer is identified by their unique address.


Since the ERC20 does not have general statistical functions,

We need to do addition and substraction in mannual for each function.
 */
contract RenewableEnergyCredits is ERC20 {

    // Whitelist, it will auto-init to false for all addresses
    // not iterable
    // Hash table
    mapping(address => bool) private isWhitelistProducer;

    // Deployer's address is the contract owner/admin
    address payable private immutable CONTRACT_OWNER;

    // per credit price
    // define the unit
    uint256 private __perCreditPrice;

    // total supply
    // init to 0 automatically
    uint256 private __totalSupply;
    // total redeemed
    // init to 0 automatically
    uint256 private __totalRedeemed;


    // Sets the per-credit price in Wei
    // and designates the deployer as admin
    constructor(uint256 initialPrice) 
    ERC20(
        "RenewableEnergyCredits",
        "REC"
    ) {
        // Set the contract deployer as the contract owner/Admin
        CONTRACT_OWNER = payable(msg.sender);

        // set the per credit price in wei
        // the uint is in wei defaultly,
        // any other unit will be converted to wei automatically
        __perCreditPrice = initialPrice;
    }

    // Producer Registration: Only the contract admin can register verified energy producers.
    // Admin Operations
    function deployerOnlyFunction() internal view{
        require(msg.sender == CONTRACT_OWNER,
         "Unauthorized: Only contract deployer(owner, admin) can perform this action"
        );
    }  

    // Whitelisted producer only
    function whitelistedProducerOnlyFunction() internal view {
        require(isWhitelistProducer[msg.sender] == true,
         "Unauthorized: Only whitelisted producer(s) can perform this action"
        );
    }

    function requireNonZeroAmountFunction(uint256 amount) internal pure {
        require(
            amount > 0,
            "Amount must be greater than zero"
        );
    }

    function requireSufficientCreditBalanceFunction(uint256 amount) internal view {
        requireNonZeroAmountFunction(amount);
        require(
            balanceOf(msg.sender) >= amount,
            "Insufficient credit balance"
        );
    }

    function requireSufficientEtherBalanceFunction(uint256 amount) internal view {
        requireNonZeroAmountFunction(amount);
        require(
            // do not test msg.sender.balance here,
            // because the sender already sent the ether to the contract
            msg.value >= amount,
            "Insufficient Ether balance"
        );
    }

    modifier deployerOnly() {
        deployerOnlyFunction();
        // Occupier of the other function
        _;
    }
    modifier whitelistedProducerOnly() {
        whitelistedProducerOnlyFunction();
        // Occupier of the other function
        _;
    }
    modifier requireNonZeroAmount(uint256 amount) {
        requireNonZeroAmountFunction(amount);
        // Occupier of the other function
        _;
    }
    modifier requireSufficientCreditBalance(uint256 amount) {
        requireSufficientCreditBalanceFunction(amount);
        // Occupier of the other function
        _;
    }
    modifier requireSufficientEtherBalance(uint256 amount) {
        requireSufficientEtherBalanceFunction(amount);
        // Occupier of the other function
        _;
    }

    // Producer Registration: Only the contract admin can register verified energy producers.
    function registerProducer(address producer)
    deployerOnly
    public {
        // set the according white list to truestorage
        isWhitelistProducer[producer] = true;
    }

    // Minting Mechanism:  Registered producers can mint (issue) new energy credits,increasing supply.
    // Enables a registered producer to create new credits
    // added to their balance and the overall supply
    function mintCredits(uint256 amount)
    whitelistedProducerOnly
    requireNonZeroAmount(amount)
    public {
        // Minting Mechanism: 
        // Registered producers can mint (issue) new energy credits, increasing supply.
        _mint(msg.sender, amount);

        // Update the total supply (mint increases total supply)
        __totalSupply += amount;
    }

    // Purchasing and Payments: Consumers may buy credits by sending Ether equal to the per-credit price.
    // Allows users to buy credits by sending Ether(must cover amount× price); 
    // purchased credits are added to the buyer’s balance
    function buyCredits(uint256 amount)
    requireSufficientEtherBalance(amount * __perCreditPrice)
    payable
    public {
        // Mint the purchased credits to the buyer's balance
        _mint(msg.sender, amount);

        // Update the total supply
        __totalSupply += amount;


        // not use receive() or fallback()
        // these are base, backup functions

        // if not received, money will stucked in the contract
        // transfer the received Ether to the contract owner/admin
        (bool success, ) = CONTRACT_OWNER.call{value: amount * __perCreditPrice}("");
        require(success, "Transfer to owner failed");
        // not use transfer, it has 2300 gas limit issue
        // CONTRACT_OWNER.transfer(amount * __perCreditPrice);
    }

    // Transfer and Redemption:  Credit holders can transfer to other users 
    // or redeem credits for carbon offsets (credits are burned).
    // Lets holders transfer credits to an-other account
    // if they have enough balance.
    function transferCredits(address to, uint256 amount)
    requireSufficientCreditBalance(amount)
    public {
        // check if the sender has enough balance
        require(balanceOf(msg.sender) >= amount, "Insufficient balance");

        // Transfer the credits
        _transfer(msg.sender, to, amount);

        // No need to update total supply, as transfer does not change total supply
    }

    // Burns credits from the caller’s balance 
    // and increases the total redeemed counter
    function redeemCredits(uint256 amount)
    requireSufficientCreditBalance(amount)
    public {
        // Check if the caller has enough balance
        require(balanceOf(msg.sender) >= amount, "Insufficient balance");

        // Burn the credits from the caller's balance
        _burn(msg.sender, amount);

        // Update the total redeemed counter
        __totalRedeemed += amount;
    }


    // Dynamic Pricing (Optional Extension): The admin could later adjust the unitprice to reflect demand;
    // this feature is optional for bonus credit.
    function setPerCreditPrice(uint256 newPerCreditPrice) deployerOnly
    public {
        // set the new per credit price in wei
        // the uint is in wei defaultly,
        // any other unit will be converted to wei automatically
        __perCreditPrice = newPerCreditPrice;
    }       

    // Market Metrics: The contract tracks total credits issued, sold,
    //  and redeemed for transparency.
    // Provides a summarized snapshot of the market’s state for dashboard queries.
    function getMarketSummary() 
    public view
    returns (
        uint256 price,
        uint256 totalSupply,
        uint256 totalRedeemed
    ) {
        // just return the initial value, it never changes
        price = __perCreditPrice;
        totalSupply = __totalSupply;
        totalRedeemed = __totalRedeemed;

        // Return the summarized market state
        return (price, totalSupply, totalRedeemed);
    }
}