"""
Test the web API endpoints
"""

import requests
import json

BASE_URL = "http://localhost:5001"

print("Testing RAG Web API")
print("=" * 60)

# Test 1: Health check
print("\n1. Testing health check endpoint...")
response = requests.get(f"{BASE_URL}/api/health")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Test 2: Chat API
print("\n2. Testing chat endpoint...")
query = "ビザウェーバープログラムとは何ですか？"
print(f"Query: {query}")

response = requests.post(
    f"{BASE_URL}/api/chat",
    json={"query": query},
    headers={"Content-Type": "application/json"}
)

print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    if data['success']:
        print(f"\nAnswer:\n{data['answer'][:300]}...")
        print(f"\nSources: {data['num_sources']} found")
        for source in data['sources'][:2]:
            print(f"  - {source['file_name']} (Page {source['page_num']})")
    else:
        print(f"Error: {data['error']}")
else:
    print(f"HTTP Error: {response.text}")

print("\n" + "=" * 60)
print("Test completed")
