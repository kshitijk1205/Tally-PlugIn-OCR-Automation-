import license_guard
import sys

print("--- CARDIOFLOW KEY MAKER ---")
print("NOTE: Copy the ID exactly as shown in the popup.")

hw_id = input("\nEnter Hardware ID: ").strip()
if hw_id:
    key = license_guard.generate_key_for_machine(hw_id)
    print(f"🔑 KEY: {key}")
    print("-" * 30)
else:
    print("No ID entered.")
    sys.exit(1)