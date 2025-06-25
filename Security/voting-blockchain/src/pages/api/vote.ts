import type { NextApiRequest, NextApiResponse } from "next";
import { votingBlockchain, Block } from "../lib/blockchain";

export default function handler(
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

        return res.status(200).json({
            message: `Vote recorded for ${candidate}`,
            chain: votingBlockchain.chain,
        });
    } else if (req.method === "GET") {
        return res.status(200).json({
            votes: votingBlockchain.countVotes(),
            chainValid: votingBlockchain.isChainValid(),
            chain: votingBlockchain.chain,
          });
    } else {
        res.setHeader("Allow", ["GET", "POST"]);
        res.status(405).end(`Method ${req.method} Not Allowed`);
    }
}
