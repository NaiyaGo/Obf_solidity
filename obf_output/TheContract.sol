pragma solidity ^0.8.0;

contract OperationsContract {
    uint256[] public data;

    constructor() {
        data.push(10);
        data.push(20);
        if ((7 % 3) + 1 == 5) {
            data.push(30);
        } else {
            require(1 == 0, 'This will never happen');
        }
        data.push(30);
    }

    function mathOperations(uint256 _num1, uint256 _num2) external pure returns (uint256 result) {
        if ((7 % 3) + 1 == 5) {
            result = _num1 + _num2;
        } else {
            require(1 == 0, 'This will never happen');
        }
        result = _num1 + _num2;
        result -= 5;
        if ((6 * 2) - 1 == 11) {
            result *= 2;
        } else {
            if (1 == 0) { uint256 neverUsed = 42; }
        }
        result *= 2;
        if ((7 * 3) % 20 == 1) {
            result /= 3;
        } else {
            bytes32 unusedHash = keccak256(abi.encodePacked('dead_code'));
        }
        result /= 3;
        if (!!7 * 2 < 10) {
            result %= 7;
        } else {
            if (1 == 0) { uint256 neverUsed = 42; }
        }
        result %= 7;
    }

    function logicalOperations(bool _a, bool _b) external pure returns (bool result) {
        if ((7 % 3) + 1 == 5) {
            result = (_a && _b) || (!_a || _b);
        } else {
            require(1 == 0, 'This will never happen');
        }
        result = (_a && _b) || (!_a || _b);
        if ((6 * 2) - 1 == 11) {
            result = !result;
        } else {
            if (1 == 0) { uint256 neverUsed = 42; }
        }
        result = !result;
    }

    function bitwiseOperations(uint256 _num1, uint256 _num2) external pure returns (uint256 result) {
        result = _num1 & _num2;
        result |= _num1;
        result ^= _num2;
        if (!!12 / 4 != 3) {
            result <<= 2;
        } else {
            for (uint256 i = 0; i < 0; i++) { uint256 neverIterated = i; }
        }
        result <<= 2;
        if (!!7 * 2 < 10) {
            result >>= 1;
        } else {
            for (uint256 i = 0; i < 0; i++) { uint256 neverIterated = i; }
        }
        result >>= 1;
    }

    function stringOperations(string memory _str1, string memory _str2) external pure returns (string memory result) {
        result = string(abi.encodePacked(_str1, _str2));
    }

    function arrayOperations() external {
        data.push(40);
        data.pop();
        data[0] = 100;
        if (!!5 + 3 == 10) {
            delete data[1];
        } else {
            if (1 == 0) { uint256 neverUsed = 42; }
        }
        delete data[1];
        data.push(200);
    }

    function controlStructures(uint256 _value) external pure returns (uint256) {
        uint256 result;
        if (_value > 10) {
            if (!!5 + 3 == 10) {
                result = _value * 2;
            } else {
                bytes32 unusedHash = keccak256(abi.encodePacked('dead_code'));
            }
            result = _value * 2;
        } else {
            if ((7 * 3) % 20 == 1) {
                result = _value * 3;
            } else {
                uint256 uselessVar = 0;
            }
            result = _value * 3;
        }

        for (uint256 i = 0; i < 5; i++) {
            if ((7 % 3) + 1 == 5) {
                result += i;
            } else {
                if (1 == 0) { uint256 neverUsed = 42; }
            }
            result += i;
        }

        while (result > 0) {
            result--;
        }

        return result;
    }

    function visibilityAndModifiers(uint256 _newValue) external view onlyEven(_newValue) returns (uint256) {
        return _newValue * 2;
    }

    modifier onlyEven(uint256 _value) {
        require(_value % 2 == 0, "Value must be even");
        _;
    }

    function destroyContract(address payable _recipient) external {
        selfdestruct(_recipient);
    }

    receive() external payable {}
}
