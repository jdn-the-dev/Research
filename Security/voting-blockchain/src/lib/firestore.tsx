import { initializeApp, getApps } from "firebase/app";
import {
    getFirestore,
    collection,
    addDoc,
    getDocs,
    orderBy,
    query,
    QueryDocumentSnapshot
} from "firebase/firestore";
import { Block, Blockchain } from "./blockchain";

// Firebase config
const firebaseConfig = {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY!,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN!,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID!,
    storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET!,
    messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID!,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID!,
};

const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
export const db = getFirestore(app);

// Load blockchain from Firestore (creates genesis if empty)
async function getBlockchainFromFirestore(): Promise<Blockchain> {
    const q = query(collection(db, "votes"), orderBy("index", "asc"));
    const snapshot = await getDocs(q);

    const blockchain = new Blockchain();
    blockchain.chain = [];

    if (snapshot.empty) {
        // Create and save the genesis block
        const genesisBlock = blockchain.createGenesisBlock();
        await addDoc(collection(db, "votes"), {
            index: genesisBlock.index,
            timestamp: genesisBlock.timestamp,
            data: genesisBlock.data,
            previousHash: genesisBlock.previousHash,
            hash: genesisBlock.hash
        });
        blockchain.chain.push(genesisBlock);
        return blockchain;
    }

    // Load existing chain from Firestore
    snapshot.forEach((doc: QueryDocumentSnapshot) => {
        const vote = doc.data();
        const block = new Block(
            vote.index,
            vote.timestamp,
            vote.data || { candidate: vote.candidate, isGenesis: vote.isGenesis },
            vote.previousHash,
            vote.hash // preserve stored hash
        );
        blockchain.chain.push(block);
    });

    return blockchain;
}

// Save a vote to Firestore
export async function saveVote(blockchain: Blockchain, candidate: string) {
    const currentChain = await getBlockchainFromFirestore();

    const newBlock = new Block(
        currentChain.chain.length,
        Date.now().toString(),
        { candidate },
        currentChain.getLatestBlock().hash
    );
    currentChain.addBlock(newBlock);

    await addDoc(collection(db, "votes"), {
        index: newBlock.index,
        timestamp: newBlock.timestamp,
        data: newBlock.data,
        previousHash: newBlock.previousHash,
        hash: newBlock.hash
    });

    return newBlock;
}

// Get votes & blockchain
export async function getVotesAndChain() {
    const blockchain = await getBlockchainFromFirestore();

    const votes: Record<string, number> = {};
    blockchain.chain.forEach((block) => {
        if (block.data.candidate) {
            votes[block.data.candidate] = (votes[block.data.candidate] || 0) + 1;
        }
    });

    return { votes, blockchain };
}
