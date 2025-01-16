use rand:: Rng;

//Function to obfuscate a string

fn obfuscate_string(input_string: &str) -> String{
    let mut random_number_generator = rand::thread_rng();
    let obfuscation_characters = ['?', '*', '\\'];
    let mut obfuscated_string = String::new();

    for character in input_string.chars() {
        let prefix_character = obfuscation_characters[random_number_generator.gen_range(0..obfuscation_characters.len())];
        let suffix_character = obfuscation_characters[random_number_generator.gen_range(0..obfuscation_characters.len())];

        obfuscated_string.push(prefix_character);
        obfuscated_string.push(character);
        obfuscated_string.push(suffix_character);
    }

    obfuscated_string
}


//Function to deobfuscate a string

fn deobfuscate_string(obfuscated_string: &str) -> String {
    let mut deobfuscated_string = String::new();
    let mut character_iterator = obfuscated_string.chars();

    while let Some(_prefix_chracter) = character_iterator.next(){
        if let Some(actual_character) = character_iterator.next(){
            if let Some(_suffix_character) = character_iterator.next(){
                deobfuscated_string.push(actual_character);
            }
        }
    }

    deobfuscated_string
}

fn main() {
 // Input string to obfuscate
 let input_string = "env:TestVariable123!";
 println!("Original: {}", input_string);

 // Obfuscate the string
 let obfuscated_string = obfuscate_string(input_string);
 println!("Obfuscated: {}", obfuscated_string);

 // Deobfuscate the string
 let deobfuscated_string = deobfuscate_string(&obfuscated_string);
 println!("Deobfuscated: {}", deobfuscated_string);
}
