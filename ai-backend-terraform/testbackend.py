# simple_test.py
import requests
import json

# Replace with your actual API endpoint from: terraform output api_endpoint
API_ENDPOINT = "https://y1hn4hs33g.execute-api.us-east-1.amazonaws.com/prod/chat"


def test_api():
    """Simple test of the API"""

    payload = {
        "messages": [
            {"role": "user", "content": "Explain quantum physics in simple terms"}
        ],
        "max_tokens": 100,
    }

    print("Sending request to API...")
    print(f"Endpoint: {API_ENDPOINT}")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")

    try:
        response = requests.post(
            API_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Success!\n")
            print(f"Response: {data['content'][0]['text']}")
            print(
                f"\nTokens - Input: {data['usage']['input_tokens']}, Output: {data['usage']['output_tokens']}"
            )
        else:
            print(f"\n❌ Error: {response.text}")

    except Exception as e:
        print(f"\n❌ Request failed: {e}")


if __name__ == "__main__":
    test_api()
