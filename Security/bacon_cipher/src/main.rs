/// A–Z → [b4,b3,b2,b1,b0]
fn char_to_bits(c: char) -> Option<[u8; 5]> {
    if !c.is_ascii_alphabetic() {
        return None;
    }
    let idx = c.to_ascii_uppercase() as u8 - b'A';
    let mut bits = [0; 5];
    for i in 0..5 {
        bits[i] = (idx >> (4 - i)) & 1;
    }
    Some(bits)
}

/// [b4,b3,b2,b1,b0] → A–Z
fn bits_to_char(bits: &[u8]) -> Option<char> {
    if bits.len() != 5 {
        return None;
    }
    let mut idx = 0;
    for (i, &b) in bits.iter().enumerate() {
        idx |= (b as u8) << (4 - i);
    }
    Some((b'A' + idx) as char)
}

/// u16 → 16 bits (big-endian)
fn u16_to_bits(n: u16) -> [u8; 16] {
    let mut bits = [0; 16];
    for i in 0..16 {
        bits[i] = ((n >> (15 - i)) & 1) as u8;
    }
    bits
}

/// 16 bits → u16
fn bits_to_u16(bits: &[u8]) -> u16 {
    let mut n = 0;
    for &b in bits.iter().take(16) {
        n = (n << 1) | (b as u16);
    }
    n
}
//Encode
fn encode(msg: &str, cover: &str) -> String {
    // build bits (header + message)
    let mut bits = u16_to_bits(msg.chars().count() as u16).to_vec();
    bits.extend(msg.chars().filter_map(char_to_bits).flat_map(|b| b));

    // count how many letters you have available
    let letters = cover.chars().filter(|c| c.is_ascii_alphabetic()).count();
    if letters < bits.len() {
        eprintln!(
            "Error: cover has only {} letters but needs {} (16+{}×5).",
            letters,
            bits.len(),
            msg.chars().count()
        );
        std::process::exit(1);
    }

    // 1) Header = msg.len() as u16 → 16 bits
    let len = msg.chars().count() as u16;
    let mut bits = u16_to_bits(len).to_vec();

    // 2) Append message bits
    bits.extend(msg.chars().filter_map(char_to_bits).flat_map(|b| b));

    // 3) Embed via casing (only consume a bit on letters)
    let mut it = bits.into_iter();
    cover
        .chars()
        .map(|c| {
            if c.is_ascii_alphabetic() {
                match it.next() {
                    Some(1) => c.to_ascii_uppercase(),
                    Some(0) => c.to_ascii_lowercase(),
                    Some(_) => c, // Handle unexpected bit values gracefully
                    None => c,
                }
            } else {
                c
            }
        })
        .collect()
}

fn decode(stego: &str) -> String {
    let bits: Vec<u8> = stego
        .chars()
        .filter_map(|c| {
            if c.is_ascii_alphabetic() {
                Some(if c.is_ascii_uppercase() { 1 } else { 0 })
            } else {
                None
            }
        })
        .collect();

    if bits.len() < 16 {
        eprintln!(
            "Error: stego text has only {} bits; need at least 16 for the header.",
            bits.len()
        );
        return String::new();
    }

    let msg_len = bits_to_u16(&bits[..16]) as usize;
    let required = 16 + msg_len * 5;
    if bits.len() < required {
        eprintln!(
            "Error: stego text has {} bits but need {} (header + {}×5).",
            bits.len(),
            required,
            msg_len
        );
        return String::new();
    }

    bits[16..required]
        .chunks(5)
        .filter_map(bits_to_char)
        .collect()
}

fn usage() {
    eprintln!("Usage:");
    eprintln!(" bacon encode <msg> <cover_text>");
    eprintln!(" bacon decode <stego_text>");
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 3 {
        usage();
        return;
    }

    match args[1].as_str() {
        "encode" => {
            if args.len() != 4 {
                usage();
                return;
            }
            println!("{}", encode(&args[2], &args[3]));
        }
        "decode" => {
            if args.len() != 3 {
                usage();
                return;
            }
            println!("{}", decode(&args[2]));
        }
        _ => usage(),
    }
}
