import asyncio
import json
import os
from dotenv import load_dotenv
from app.services.nango_service import NangoService

# Load environment variables
load_dotenv()

# Initialize the Nango service
nango_service = NangoService()

async def test_zoho_endpoint(connection_id, endpoint_name, method, entity_id=None, params=None):
    print(f"\n🔍 Testing Zoho {endpoint_name} API...")
    try:
        if entity_id:
            result = await method(connection_id, entity_id)
        else:
            result = await method(connection_id, params)
            
        print(f"✅ Success! Received data from {endpoint_name} API")
        print("\nResponse data:")
        print(json.dumps(result, indent=2))
        return result
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

async def main():
    print("=== Zoho API Integration Test ===\n")
    
    # Check if Nango secret key is set
    nango_secret_key = os.getenv("NANGO_SECRET_KEY")
    if nango_secret_key == "your_nango_secret_key" or not nango_secret_key:
        print("⚠️ Warning: You need to set a valid NANGO_SECRET_KEY in your .env file")
        update_key = input("Would you like to enter your Nango secret key now? (y/n): ")
        if update_key.lower() == 'y':
            nango_secret_key = input("Enter your Nango secret key: ")
            # Update the service with the new key
            nango_service.secret_key = nango_secret_key
            nango_service.headers = {
                "Authorization": f"Bearer {nango_secret_key}",
                "Content-Type": "application/json"
            }
        else:
            print("Please update your .env file with your actual Nango secret key")
            return
    
    # Get connection ID
    connection_id = input("Enter your Nango connection ID for Zoho: ")
    if not connection_id:
        print("Connection ID is required")
        return
    
    while True:
        print("\n=== Available Zoho Endpoints ===")
        print("1. Contacts")
        print("2. Accounts")
        print("3. Leads")
        print("4. Deals")
        print("5. Products")
        print("6. Users")
        print("7. Get specific entity by ID")
        print("8. Exit")
        
        choice = input("\nSelect an endpoint to test (1-8): ")
        
        if choice == "1":
            await test_zoho_endpoint(connection_id, "Contacts", nango_service.get_zoho_contacts)
        elif choice == "2":
            await test_zoho_endpoint(connection_id, "Accounts", nango_service.get_zoho_accounts)
        elif choice == "3":
            await test_zoho_endpoint(connection_id, "Leads", nango_service.get_zoho_leads)
        elif choice == "4":
            await test_zoho_endpoint(connection_id, "Deals", nango_service.get_zoho_deals)
        elif choice == "5":
            await test_zoho_endpoint(connection_id, "Products", nango_service.get_zoho_products)
        elif choice == "6":
            await test_zoho_endpoint(connection_id, "Users", nango_service.get_zoho_users)
        elif choice == "7":
            entity_type = input("Enter entity type (contacts, accounts, leads, deals, products, users): ").lower()
            entity_id = input("Enter entity ID: ")
            
            if not entity_id:
                print("Entity ID is required")
                continue
                
            method_mapping = {
                "contacts": nango_service.get_zoho_contact_by_id,
                "accounts": nango_service.get_zoho_account_by_id,
                "leads": nango_service.get_zoho_lead_by_id,
                "deals": nango_service.get_zoho_deal_by_id,
                "products": nango_service.get_zoho_product_by_id,
                "users": nango_service.get_zoho_user_by_id
            }
            
            if entity_type not in method_mapping:
                print(f"Unknown entity type: {entity_type}")
                print(f"Available types: {', '.join(method_mapping.keys())}")
                continue
                
            await test_zoho_endpoint(connection_id, f"{entity_type.capitalize()} by ID", 
                                    method_mapping[entity_type], entity_id)
        elif choice == "8":
            print("\nExiting test script. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())