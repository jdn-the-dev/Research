import type { NextApiRequest, NextApiResponse } from "next";
import { votingBlockchain, Block } from "@/lib/blockchain";
// Firebase imports
import { initializeApp, getApps } from "firebase/app";
import { getFirestore, collection, addDoc, getDocs } from "firebase/firestore";

// Firebase config (replace with your actual config)
const firebaseConfig = {
    apiKey: process.env.FIREBASE_API_KEY,
    authDomain: process.env.FIREBASE_AUTH_DOMAIN,
    projectId: process.env.FIREBASE_PROJECT_ID,
    storageBucket: process.env.FIREBASE_STORAGE_BUCKET,
    messagingSenderId: process.env.FIREBASE_MESSAGING_SENDER_ID,
    appId: process.env.FIREBASE_APP_ID
};

// Initialize Firebase app and Firestore
const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
const db = getFirestore(app);

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    if (req.method === "POST") {
        const { candidate } = req.body;

        if (!candidate) {
            return res.status(400).json({ error: "Candidate name required." });
        }

        const newBlock = new Block(
            votingBlockchain.chain.length,
            Date.now().toString(),
            { candidate }
        );

        votingBlockchain.addBlock(newBlock);

        // Store vote in Firestore
        try {
            await addDoc(collection(db, "votes"), {
                index: newBlock.index,
                timestamp: newBlock.timestamp,
                candidate,
                previousHash: newBlock.previousHash,
                hash: newBlock.hash,
            });
        } catch (error) {
            return res.status(500).json({ error: "Failed to store vote in Firebase." });
        }

        return res.status(200).json({
            message: `Vote recorded for ${candidate}`,
            chain: votingBlockchain.chain,
        });
    } else if (req.method === "GET") {
        // Read votes from Firestore
        try {
            const snapshot = await getDocs(collection(db, "votes"));
            const votesArr: any[] = [];
            snapshot.forEach(doc => votesArr.push(doc.data()));

            // If Firestore is empty, return genesis block and empty votes
            if (votesArr.length === 0) {
                const genesisBlock = votingBlockchain.chain[0];
                return res.status(200).json({
                    votes: {}, // always an object
                    chainValid: true,
                    chain: [genesisBlock],
                    firebaseVotes: [],
                    message: "No votes yet. Only genesis block present."
                });
            }

            // Count votes from Firestore data
            const votes: Record<string, number> = {};
            votesArr.forEach((vote) => {
                if (vote.candidate) {
                    votes[vote.candidate] = (votes[vote.candidate] || 0) + 1;
                }
            });

            // Always include genesis block at the start of chain
            const chainWithGenesis = [
                votingBlockchain.chain[0],
                ...votesArr.map(vote => ({
                    index: vote.index,
                    timestamp: vote.timestamp,
                    data: { candidate: vote.candidate },
                    previousHash: vote.previousHash,
                    hash: vote.hash
                }))
            ];

            return res.status(200).json({
                votes,
                chainValid: votingBlockchain.isChainValid(),
                chain: chainWithGenesis,
                firebaseVotes: votesArr,
            });
        } catch (error) {
            return res.status(500).json({ error: "Failed to read votes from Firebase." });
        }
    } else {
        res.setHeader("Allow", ["GET", "POST"]);
        res.status(405).end(`Method ${req.method} Not Allowed`);
    }
}
