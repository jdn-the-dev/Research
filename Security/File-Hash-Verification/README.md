
# File Hash Verification

This project consists of programs to generate and verify file hashes using HMAC (Hash-based Message Authentication Code). The repository is divided into two key programs:

1. **Hash Generation Program:** Computes a hash for each file in a directory and saves it to another directory.
2. **Hash Verification Program:** Compares the stored hash values against freshly computed ones to verify file integrity.

---

## Features

- Computes secure HMAC-SHA256 hash values.
- Automatically generates hash files for every file in the source directory.
- Verification mode to check file integrity and detect any changes.
- Customizable secret key for HMAC hashing.

---

## Requirements

- Python 3.8 or higher

---

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/jdn-the-dev/Research.git
   cd Research/Security/File-Hash-Verification
   ```

2. Ensure Python is installed on your system:

   ```bash
   python --version
   ```

3. Install required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

---

## Usage

This program can be run in two modes: `generate` and `verify`.

### 1. Generate Hashes

To generate hash files for all files in a directory:

```bash
python main.py generate <directory1> <directory2>
```

- **directory1**: Source directory containing the files.
- **directory2**: Target directory where the hash files will be saved.

Example:

```bash
python main.py generate ./source_files ./hashes
```

### 2. Verify Hashes

To verify if the current files match their stored hash values:

```bash
python main.py verify <directory1> <directory2>
```

- **directory1**: Source directory containing the files.
- **directory2**: Directory containing the previously generated hash files.

Example:

```bash
python main.py verify ./source_files ./hashes
```

---

## Project Structure

```
File-Hash-Verification/
├── program.py          # Main Python script
├── README.md           # Documentation
└── requirements.txt    # Contains required dependencies
```

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Submit a pull request with a detailed explanation.

---

## License

This project is licensed under the MIT License. See [LICENSE](./LICENSE) for more details.

---

## Contact

If you have any questions or suggestions, feel free to reach out.

---

**All the best!** 🎉
