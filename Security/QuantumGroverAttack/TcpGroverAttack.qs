namespace TcpQuantumAttack {
    open Microsoft.Quantum.Intrinsic;
    open Microsoft.Quantum.Canon;
    open Microsoft.Quantum.Measurement;
    open Microsoft.Quantum.Convert;
    open Microsoft.Quantum.Math;
    open Microsoft.Quantum.Arrays;

    // --------------------------------------
    // Oracle: flips the phase of |target⟩
    // --------------------------------------
    operation TcpOracle(target : Int, register : Qubit[]) : Unit is Adj + Ctl {
        let n = Length(register);
        let targetBits = IntAsBoolArray(target, n);

        // Apply X to all qubits where target bit = 0
        for i in 0 .. n-1 {
            if (not targetBits[i]) {
                X(register[i]);
            }
        }

        // Multi-controlled Z (phase flip)
        Controlled Z(Most(register), Tail(register));

        // Undo the X gates
        for i in 0 .. n-1 {
            if (not targetBits[i]) {
                X(register[i]);
            }
        }
    }

    // --------------------------------------
    // Grover diffusion operator
    // --------------------------------------
    operation Diffusion(register : Qubit[]) : Unit is Adj + Ctl {
        ApplyToEachCA(H, register);
        ApplyToEachCA(X, register);

        Controlled Z(Most(register), Tail(register));

        ApplyToEachCA(X, register);
        ApplyToEachCA(H, register);
    }

    // --------------------------------------
    // Classical brute force attack
    // --------------------------------------
    operation RunClassicalBruteForce(target : Int, nQubits : Int) : (Int, Int) {
        let maxValue = 2 ^ nQubits;
        mutable attempts = 0;
        mutable found = -1;

        // Simulate checking each possible value sequentially
        for guess in 0 .. maxValue - 1 {
            set attempts = attempts + 1;
            if guess == target {
                set found = guess;
                Message($"Classical brute force found {target} after {attempts} attempts");
                return (found, attempts);
            }
        }

        return (found, attempts);
    }

    // --------------------------------------
    // Main attack simulation
    // --------------------------------------
    @EntryPoint()
    operation Main() : Int {
        let nQubits = 8;           // 8-bit simulation
        let target = 137;          // pretend TCP sequence number

        Message($"\n========================================");
        Message($"TCP Sequence Number Attack Comparison");
        Message($"========================================");
        Message($"Target TCP Sequence Number: {target}");
        Message($"Search Space: {2 ^ nQubits} possibilities ({nQubits} bits)");
        Message($"");

        // Classical brute force attack
        Message($"--- Classical Brute Force Attack ---");
        let (classicalResult, attempts) = RunClassicalBruteForce(target, nQubits);
        Message($"Result: {classicalResult}");
        Message($"");

        // Quantum Grover attack
        Message($"--- Quantum Grover Attack ---");
        let quantumResult = RunTcpSequenceGrover(target, nQubits);
        Message($"Quantum Guess: {quantumResult}");
        Message($"");

        // Comparison
        Message($"========================================");
        Message($"Comparison:");
        Message($"  Classical attempts: {attempts}");
        let N = 2 ^ nQubits;
        let groverIterations = Round(PI() / 4.0 * Sqrt(IntAsDouble(N)));
        Message($"  Grover iterations: {groverIterations}");
        let speedup = IntAsDouble(attempts) / IntAsDouble(groverIterations);
        Message($"  Quantum speedup: ~{speedup}x faster");
        Message($"  Classical match: {classicalResult == target}");
        Message($"  Quantum match: {quantumResult == target}");
        Message($"========================================");

        return quantumResult;
    }

    operation RunTcpSequenceGrover(target : Int, nQubits : Int) : Int {

        use register = Qubit[nQubits];

        // 1. Put qubits into uniform superposition
        ApplyToEach(H, register);

        // 2. Compute number of Grover iterations
        let N = 2 ^ nQubits;
        let iterations = Round(PI() / 4.0 * Sqrt(IntAsDouble(N)));

        Message($"Running Grover with {iterations} iterations...");

        // 3. Run Grover iteration
        for _ in 1 .. iterations {
            TcpOracle(target, register);
            Diffusion(register);
        }

        // 4. Measure result
        let result = ResultArrayAsInt(ForEach(M, register));

        ResetAll(register);
        return result;
    }
}
