import os
import requests

class TranslatorEngine:
    def __init__(self, source="ja", target="zh", use_ollama=True, model="hy-mt2-1.8b"):
        """
        Translator using Tencent HY-MT2 via local Ollama.
        """
        # Clear proxy for local requests
        os.environ.pop('http_proxy', None)
        os.environ.pop('https_proxy', None)
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)

        self.model = model
        print(f"Translation model: {model} (via Ollama)")

    def translate(self, text):
        if not text or not text.strip():
            return ""

        try:
            prompt = f"Translate the following Japanese text to Simplified Chinese directly. Output ONLY the translation.\n\n{text}"

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 2048,
                    "stop": ["\n"]
                }
            }

            response = requests.post(
                "http://127.0.0.1:11434/api/generate",
                json=payload,
                timeout=30,
                proxies={"http": None, "https": None}
            )

            if response.status_code == 200:
                result = response.json().get("response", "").strip()
                result = result.split("\n")[0].strip()

                # Clean common prefixes
                prefixes_to_clean = ["日语：", "中文：", "翻译：", "中文翻译：", "日语:", "中文:", "翻译:", "中文翻译:"]
                for prefix in prefixes_to_clean:
                    if result.startswith(prefix):
                        result = result[len(prefix):].strip()

                return result if result else text
            else:
                print(f"Ollama error: {response.status_code}")
                return text

        except requests.exceptions.ConnectionError:
            print("Ollama not running, translation failed")
            return text
        except Exception as e:
            print(f"Translation error: {e}")
            return text
