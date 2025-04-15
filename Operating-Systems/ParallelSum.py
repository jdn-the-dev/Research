import multiprocessing  # For handling multiple processes
import threading  # For handling multiple threads within a process

def calculate_sum(arr, result, index):
    """Thread function to compute sum of an array segment."""
    result[index] = sum(arr)
    print(f"Thread {index+1}: Sum = {result[index]}")

def process_task(segment, result, index):
    """Process function that spawns two threads."""
    print(f"Process {index+1} started.")

    # Split the segment and create two threads
    thread1 = threading.Thread(target=calculate_sum, args=(segment[:len(segment)//2], result, index*2))
    thread2 = threading.Thread(target=calculate_sum, args=(segment[len(segment)//2:], result, index*2+1))

    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()

    print(f"Process {index+1} completed.")

if __name__ == "__main__":
    data = list(range(1, 21))  # Sample dataset
    manager = multiprocessing.Manager()
    result = manager.list([0] * 4)  # Shared memory for results

    # Create and start two processes
    process1 = multiprocessing.Process(target=process_task, args=(data[:10], result, 0))
    process2 = multiprocessing.Process(target=process_task, args=(data[10:], result, 1))

    process1.start()
    process2.start()
    process1.join()
    process2.join()

    print(f"Final Sum: {sum(result)}")
