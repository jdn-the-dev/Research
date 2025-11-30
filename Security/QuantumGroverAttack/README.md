# Quantum Grover Attack on TCP Sequence Numbers

A demonstration comparing classical brute force vs. quantum Grover's algorithm for attacking TCP sequence number prediction.

## Overview

This project demonstrates the quantum advantage by comparing:
- **Classical Brute Force**: O(N) complexity - checks each possibility sequentially
- **Grover's Algorithm**: O(√N) complexity - quantum speedup for unstructured search

For an 8-bit search space (256 possibilities), the classical approach requires ~138 attempts on average, while Grover's algorithm needs only ~13 iterations - approximately **10x faster**!

## Prerequisites

### Required Software

1. **.NET SDK 6.0 or later**
   - Download from: https://dotnet.microsoft.com/download
   - Verify installation:
     ```bash
     dotnet --version
     ```

2. **Microsoft Quantum Development Kit**
   - The QDK is automatically installed via the project's NuGet package
   - No separate installation needed

### Optional (Recommended)

- **Visual Studio Code** with the Q# extension
  - Install VS Code: https://code.visualstudio.com/
  - Install Q# extension from the marketplace

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/jdn-the-dev/Research.git
cd Research/Security/QuantumGroverAttack
```

### 2. Restore Dependencies

```bash
dotnet restore
```

This will download the Microsoft Quantum SDK and all required packages.

### 3. Build the Project

```bash
dotnet build
```

You should see output similar to:
```
Build succeeded.
    0 Warning(s)
    0 Error(s)
```

## Running the Program

### Basic Execution

From the project directory:

```bash
dotnet run
```

Or run directly:

```bash
dotnet run --project QuantumGroverAttack.csproj
```

### Expected Output

```
========================================
TCP Sequence Number Attack Comparison
========================================
Target TCP Sequence Number: 137
Search Space: 256 possibilities (8 bits)

--- Classical Brute Force Attack ---
Classical brute force found 137 after 138 attempts
Result: 137

--- Quantum Grover Attack ---
Running Grover with 13 iterations...
Quantum Guess: 137

========================================
Comparison:
  Classical attempts: 138
  Grover iterations: 13
  Quantum speedup: ~10.6x faster
  Classical match: true
  Quantum match: true
========================================
```

## Project Structure

```
QuantumGroverAttack/
├── TcpGroverAttack.qs          # Main Q# implementation
├── QuantumGroverAttack.csproj  # Project configuration
└── README.md                    # This file
```

## Code Components

### 1. TcpOracle (Lines 12-30)
The quantum oracle that marks the target state by flipping its phase. This is the "black box" that identifies our target TCP sequence number.

### 2. Diffusion (Lines 35-43)
The Grover diffusion operator (also called inversion about average) that amplifies the amplitude of the marked state.

### 3. RunClassicalBruteForce (Lines 48-64)
Classical sequential search implementation for comparison purposes.

### 4. RunTcpSequenceGrover (Lines 109-133)
The quantum Grover's algorithm implementation:
- Creates uniform superposition
- Applies Grover iterations
- Measures the result

### 5. Main (Lines 70-107)
Entry point that runs both attacks and compares results.

## Customization

### Change the Search Space

Edit `TcpGroverAttack.qs` line 71:

```qsharp
let nQubits = 8;  // Change to 10 for 1024 possibilities, 12 for 4096, etc.
```

### Change the Target

Edit `TcpGroverAttack.qs` line 72:

```qsharp
let target = 137;  // Any number within your search space
```

### Example: 10-bit Search

```qsharp
let nQubits = 10;   // 1024 possibilities
let target = 512;   // Target value
```

This would require ~512 classical attempts vs. ~25 Grover iterations (~20x speedup).

## Understanding the Results

### Quantum Speedup

The speedup grows with search space size:

| Search Space | Classical Avg | Grover Iterations | Speedup |
|--------------|---------------|-------------------|---------|
| 2^8 (256)    | ~138          | ~13              | ~10x    |
| 2^10 (1024)  | ~512          | ~25              | ~20x    |
| 2^12 (4096)  | ~2048         | ~51              | ~40x    |
| 2^16 (65536) | ~32768        | ~201             | ~163x   |

### Why Grover's Algorithm Works

1. **Superposition**: Places all possible values in quantum superposition
2. **Oracle**: Marks the target state with a phase flip
3. **Diffusion**: Amplifies the marked state's amplitude
4. **Iteration**: Repeating oracle + diffusion increases probability of measuring the target
5. **Measurement**: Collapses to the target state with high probability

## Troubleshooting

### Build Errors

**Error: SDK not found**
```bash
dotnet --list-sdks
```
Ensure .NET 6.0 or later is installed.

**Error: QDK package not found**
```bash
dotnet restore --force
dotnet build
```

### Runtime Errors

**Error: Operation not found**
- Ensure all namespaces are properly imported
- Check that `TcpGroverAttack.qs` has no syntax errors

**Incorrect results**
- Grover's algorithm is probabilistic; re-run for different outcomes
- Increase iterations slightly if success rate is low

## Educational Purpose

This project is for **educational and research purposes only** to demonstrate:
- Quantum computing concepts
- Grover's algorithm implementation
- Quantum vs. classical complexity comparison

**Note**: Real TCP sequence numbers use 32-bit values and additional protections. This is a simplified demonstration of quantum search algorithms.

## Resources

- [Microsoft Quantum Documentation](https://docs.microsoft.com/quantum/)
- [Grover's Algorithm Explained](https://qiskit.org/textbook/ch-algorithms/grover.html)
- [Q# Language Reference](https://docs.microsoft.com/quantum/user-guide/)

## License

This is a demonstration project for educational purposes.

## Quick Start (TL;DR)

```bash
# Clone the repository
git clone https://github.com/jdn-the-dev/Research.git
cd Research/Security/QuantumGroverAttack

# Restore, build, and run
dotnet restore
dotnet build
dotnet run
```

## Further Exploration

### Try Different Scenarios

1. **Increase qubit count** to see how speedup scales
2. **Run multiple times** to observe probabilistic nature
3. **Modify the oracle** to search for different patterns
4. **Add error handling** for edge cases

### Next Steps

- Implement amplitude amplification variants
- Add visualization of quantum state evolution
- Compare with other quantum search algorithms
- Explore real-world quantum computing platforms (IBM Q, Azure Quantum)

## Contributing

Contributions are welcome! Feel free to:
- Report issues
- Suggest improvements
- Submit pull requests
- Add additional quantum algorithms for comparison
