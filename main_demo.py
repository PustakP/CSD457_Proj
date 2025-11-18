"""
main demo script - quantum-safe crypto for iot
demonstrates all approaches and compares performance
"""
import sys
from full_kyber import demo_full_kyber
from hybrid_kyber_aes import demo_hybrid
from proxy_reencryption import demo_proxy_reencryption
from performance_analysis import run_complete_analysis


def print_menu():
    """display main menu"""
    print("\n" + "=" * 80)
    print("quantum-safe cryptography for iot devices".upper().center(80))
    print("=" * 80)
    print("\nselect a demo to run:\n")
    print("  1. full kyber encryption demo")
    print("     - pure kyber kem approach")
    print("     - quantum-safe but computationally intensive")
    print()
    print("  2. hybrid kyber-aes demo")
    print("     - kyber kem for key exchange + aes for encryption")
    print("     - balanced security and performance")
    print()
    print("  3. proxy re-encryption demo")
    print("     - fog computing architecture")
    print("     - gateway transforms encryption w/o decryption")
    print()
    print("  4. run complete performance analysis")
    print("     - compare all approaches")
    print("     - device suitability analysis")
    print("     - generate detailed report")
    print()
    print("  5. run all demos sequentially")
    print()
    print("  0. exit")
    print("\n" + "=" * 80)


def run_all_demos():
    """run all demos in sequence"""
    print("\n" + "=" * 80)
    print("running all demonstrations".upper().center(80))
    print("=" * 80)
    
    print("\n\n")
    input("press enter to start demo 1: full kyber encryption...")
    demo_full_kyber()
    
    print("\n\n")
    input("press enter to start demo 2: hybrid kyber-aes...")
    demo_hybrid()
    
    print("\n\n")
    input("press enter to start demo 3: proxy re-encryption...")
    demo_proxy_reencryption()
    
    print("\n\n")
    input("press enter to start performance analysis...")
    run_complete_analysis()
    
    print("\n" + "=" * 80)
    print("all demonstrations completed!".upper().center(80))
    print("=" * 80)


def main():
    """main entry point"""
    while True:
        print_menu()
        
        try:
            choice = input("enter your choice (0-5): ").strip()
            
            if choice == '0':
                print("\nexiting... stay quantum-safe!")
                sys.exit(0)
            
            elif choice == '1':
                demo_full_kyber()
                input("\npress enter to continue...")
            
            elif choice == '2':
                demo_hybrid()
                input("\npress enter to continue...")
            
            elif choice == '3':
                demo_proxy_reencryption()
                input("\npress enter to continue...")
            
            elif choice == '4':
                run_complete_analysis()
                input("\npress enter to continue...")
            
            elif choice == '5':
                run_all_demos()
                input("\npress enter to return to menu...")
            
            else:
                print("\ninvalid choice. please select 0-5.")
                input("press enter to continue...")
        
        except KeyboardInterrupt:
            print("\n\nexiting... stay quantum-safe!")
            sys.exit(0)
        except Exception as e:
            print(f"\nerror: {e}")
            input("press enter to continue...")


if __name__ == "__main__":
    main()

