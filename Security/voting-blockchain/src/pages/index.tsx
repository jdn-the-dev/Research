import { useEffect, useState } from "react";
import { votingBlockchain } from "@/lib/blockchain";
import { saveVote, getVotesAndChain } from "@/lib/firestore";

type Block = {
  index: number;
  timestamp: string;
  data: { candidate?: string; isGenesis?: boolean };
  previousHash: string;
  hash: string;
};

export default function Home() {
  const [candidate, setCandidate] = useState<string>("");
  const [message, setMessage] = useState<string>("");
  const [votes, setVotes] = useState<Record<string, number>>({});
  const [chain, setChain] = useState<Block[]>([]);
  const [chainValid, setChainValid] = useState<boolean>(true);
  const [isVoting, setIsVoting] = useState<boolean>(false);

  const credit = process.env.NEXT_PUBLIC_PROJECT_CREDIT;

  const submitVote = async () => {
    if (!candidate.trim()) {
      alert("Please enter a candidate name.");
      return;
    }
    setIsVoting(true);
    try {
      await saveVote(votingBlockchain, candidate);
      setMessage(`Your vote for "${candidate}" was recorded successfully!`);
      setCandidate("");
      fetchVotes();
    } catch (error) {
      console.error(error);
      setMessage("Error submitting vote.");
    } finally {
      setIsVoting(false);
    }
  };

  const fetchVotes = async () => {
    try {
      const { votes, blockchain } = await getVotesAndChain();
      setVotes(votes);
      setChain(blockchain.chain);
      setChainValid(blockchain.isChainValid());
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchVotes();
  }, []);

  return (
    <div style={styles.container}>
      <div
        style={{
          marginBottom: "16px",
          color: "#666666",
          fontSize: "1rem",
          textAlign: "center",
        }}
      >
        <em>{credit}</em>
      </div>

      <h1 style={styles.title}>Blockchain Voting System</h1>

      <div style={styles.inputContainer}>
        <input
          type="text"
          placeholder="Enter candidate name"
          value={candidate}
          onChange={(e) => setCandidate(e.target.value)}
          style={styles.input}
        />
        <button
          onClick={submitVote}
          disabled={isVoting}
          style={{
            ...styles.button,
            backgroundColor: isVoting ? "#888888" : "#0070f3",
            cursor: isVoting ? "not-allowed" : "pointer",
          }}
        >
          {isVoting ? "Submitting..." : "Vote"}
        </button>
      </div>

      {message && <p style={styles.message}>{message}</p>}

      <h2 style={styles.subtitle}>Current Votes</h2>
      <div style={styles.grid}>
        {votes && typeof votes === "object" && Object.entries(votes).length > 0 ? (
          Object.entries(votes).map(([name, count]) => (
            <div key={name} style={styles.card}>
              <h3>{name}</h3>
              <p>
                {count} vote{count !== 1 ? "s" : ""}
              </p>
            </div>
          ))
        ) : (
          <div style={styles.card}>No votes yet.</div>
        )}
      </div>

      <h2 style={styles.subtitle}>Blockchain Data</h2>
      <div style={styles.chain}>
        {Array.isArray(chain) && chain.length > 0 ? (
          chain.map((block) => (
            <div key={block.hash} style={styles.block}>
              <p><strong>Block:</strong> {block.index}</p>
              <p><strong>Timestamp:</strong> {new Date(Number(block.timestamp)).toLocaleString()}</p>
              <p><strong>Data:</strong> {block.data.isGenesis ? "Genesis Block" : block.data.candidate}</p>
              <p><strong>Previous Hash:</strong><br /> {block.previousHash}</p>
              <p><strong>Hash:</strong><br /> {block.hash}</p>
            </div>
          ))
        ) : (
          <div style={styles.block}>No blocks yet.</div>
        )}
      </div>

      <h3 style={styles.integrity}>
        Blockchain Integrity: {chainValid ? "Valid" : "Corrupted"}
      </h3>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: "40px",
    fontFamily: "Arial, sans-serif",
    maxWidth: "1000px",
    margin: "0 auto",
    backgroundColor: "#ffffff", // fixed background
    color: "#000000",           // fixed text color
    colorScheme: "light",       // prevent system theme switching
  },
  title: {
    textAlign: "center",
    fontSize: "2.5rem",
    marginBottom: "20px",
    color: "#333333",
  },
  subtitle: {
    marginTop: "40px",
    fontSize: "1.8rem",
    color: "#222222",
  },
  inputContainer: {
    display: "flex",
    gap: "10px",
    marginBottom: "10px",
  },
  input: {
    flex: 1,
    padding: "10px",
    borderRadius: "8px",
    border: "1px solid #cccccc",
    fontSize: "1rem",
    backgroundColor: "#ffffff",
    color: "#000000",
  },
  button: {
    padding: "10px 20px",
    borderRadius: "8px",
    border: "none",
    color: "#ffffff",
    fontWeight: "bold",
    fontSize: "1rem",
    transition: "background-color 0.3s ease",
  },
  message: {
    margin: "10px 0",
    color: "#0070f3",
    fontWeight: "bold",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "20px",
    marginTop: "20px",
  },
  card: {
    padding: "20px",
    border: "1px solid #eeeeee",
    borderRadius: "12px",
    boxShadow: "0 4px 10px rgba(0,0,0,0.05)",
    textAlign: "center",
    backgroundColor: "#fafafa",
    color: "#000000",
  },
  chain: {
    marginTop: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  block: {
    padding: "20px",
    border: "1px solid #dddddd",
    borderRadius: "10px",
    backgroundColor: "#f9f9f9",
    color: "#000000",
    boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
    wordBreak: "break-word",
    fontSize: "0.9rem",
  },
  integrity: {
    marginTop: "50px",
    fontSize: "1.2rem",
    color: "#555555",
    textAlign: "center",
  },
};
