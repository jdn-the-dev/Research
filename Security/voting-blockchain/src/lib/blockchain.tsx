import crypto from "crypto";

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
        previousHash = "",
        storedHash?: string // optional hash from Firestore
    ) {
        this.index = index;
        this.timestamp = timestamp;
        this.data = data;
        this.previousHash = previousHash;
        this.hash = storedHash || this.calculateHash(); // use stored hash if available
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
        this.chain = [this.createGenesisBlock()];
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
}

export const votingBlockchain = new Blockchain();
