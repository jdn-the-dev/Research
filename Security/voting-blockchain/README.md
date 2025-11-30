## Quick Start

```bash
# 1 · Clone the project
git clone https://github.com/jdn-the-dev/voting-blockchain.git
cd voting-blockchain

# 2 · Install dependencies
npm install          # or: yarn / pnpm / bun install

# 3 · Run the dev server
npm run dev          # or: yarn dev / pnpm dev / bun dev
```

## 🌐 Firebase Hosting & Persistence

1. Create a Firebase project at [Firebase Console](https://console.firebase.google.com/).
2. Install Firebase CLI:
    ```bash
    npm install -g firebase-tools
    ```
3. Login to Firebase:
    ```bash
    firebase login
    ```
4. Initialize Firebase in your project directory:
    ```bash
    firebase init
    ```
    - Select **Hosting** and **Firestore** (for persistent data).
    - Use `build` as your public directory if using a build step.
    - Configure as a single-page app if needed.

5. Add your Firebase config to your app (see Firebase docs for details).

6. Deploy:
    ```bash
    firebase deploy
    ```

## 🔗 References

- [Firebase Hosting Docs](https://firebase.google.com/docs/hosting)
- [Firebase Firestore Docs](https://firebase.google.com/docs/firestore)