import crypto from "crypto";
import fs from "fs";
import path from "path";

const DATA_PATH = path.join(process.cwd(), "data");
const FILE_PATH = path.join(DATA_PATH, "blockchain.json");

export interface BlockData {
    candidate?: string;
    isGenesis?: boolean;
}

export class Block {
    index: number;
    timestamp: string;
    data: BlockData;
    previousHash: string;
    hash: string;

    constructor(
        index: number,
        timestamp: string,
        data: BlockData,
        previousHash = ""
    ) {
        this.index = index;
        this.timestamp = timestamp;
        this.data = data;
        this.previousHash = previousHash;
        this.hash = this.calculateHash();
    }

    calculateHash(): string {
        return crypto
            .createHash("sha256")
            .update(
                this.index +
                this.previousHash +
                this.timestamp +
                JSON.stringify(this.data)
            )
            .digest("hex");
    }
}

export class Blockchain {
    chain: Block[];

    constructor() {
        this.chain = this.loadChain();
    }

    createGenesisBlock(): Block {
        return new Block(0, Date.now().toString(), { isGenesis: true }, "0");
    }

    getLatestBlock(): Block {
        return this.chain[this.chain.length - 1];
    }

    addBlock(newBlock: Block): void {
        newBlock.previousHash = this.getLatestBlock().hash;
        newBlock.hash = newBlock.calculateHash();
        this.chain.push(newBlock);
        this.saveChain();
    }

    isChainValid(): boolean {
        for (let i = 1; i < this.chain.length; i++) {
            const current = this.chain[i];
            const previous = this.chain[i - 1];

            if (current.hash !== current.calculateHash()) {
                return false;
            }

            if (current.previousHash !== previous.hash) {
                return false;
            }
        }
        return true;
    }

    countVotes(): Record<string, number> {
        const votes: Record<string, number> = {};
        this.chain.forEach((block) => {
            if (block.data.candidate) {
                const candidate = block.data.candidate;
                votes[candidate] = (votes[candidate] || 0) + 1;
            }
        });
        return votes;
    }

    saveChain(): void {
        if (!fs.existsSync(DATA_PATH)) {
            fs.mkdirSync(DATA_PATH);
        }
        fs.writeFileSync(FILE_PATH, JSON.stringify(this.chain, null, 2));
    }

    loadChain(): Block[] {
        if (fs.existsSync(FILE_PATH)) {
            const data = fs.readFileSync(FILE_PATH, "utf-8");
            const parsed = JSON.parse(data);
            return parsed.map(
                (block: any) =>
                    new Block(
                        block.index,
                        block.timestamp,
                        block.data,
                        block.previousHash
                    )
            );
        } else {
            return [this.createGenesisBlock()];
        }
    }
}

export const votingBlockchain = new Blockchain();
