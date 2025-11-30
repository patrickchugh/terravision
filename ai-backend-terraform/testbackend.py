# simple_test.py
import requests
import json

# Replace with your actual API endpoint from: terraform output api_endpoint


API_ENDPOINT = "https://yirz70b5mc.execute-api.us-east-1.amazonaws.com/prod/chat"


def test_api():
    """Simple test of the streaming API"""

    payload = {
        "messages": [
            {"role": "user", "content": "Explain quantum physics in simple terms"}
        ],
        "max_tokens": 1000,
    }

    print("Sending request to API...")
    print(f"Endpoint: {API_ENDPOINT}")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")

    try:
        response = requests.post(
            API_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=60,
        )

        print(f"Status Code: {response.status_code}\n")

        if response.status_code == 200:
            print("✅ Streaming response:\n")
            full_response = ""
            for chunk in response.iter_content(chunk_size=1, decode_unicode=False):
                if chunk:
                    text = chunk.decode("utf-8", errors="ignore")
                    print(text, end="", flush=True)
                    full_response += text
            print("\n\n✅ Stream complete!")
            print(f"Total characters received: {len(full_response)}")
        else:
            print(f"\n❌ Error: {response.text}")

    except Exception as e:
        print(f"\n❌ Request failed: {e}")


if __name__ == "__main__":
    test_api()
