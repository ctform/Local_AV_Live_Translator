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

    def _clean_result(self, result):
        result = (result or "").strip().split("\n")[0].strip()
        prefixes_to_clean = ["日语：", "中文：", "翻译：", "中文翻译：", "日语:", "中文:", "翻译:", "中文翻译:"]
        for prefix in prefixes_to_clean:
            if result.startswith(prefix):
                result = result[len(prefix):].strip()
        return result

    def translate(self, text):
        if not text or not text.strip():
            return ""

        try:
            prompt = f"Translate the following Japanese text to Simplified Chinese directly. Output ONLY the translation.\n\n{text}"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_ctx": 2048, "stop": ["\n"]}
            }
            response = requests.post(
                "http://127.0.0.1:11434/api/generate", json=payload,
                timeout=30, proxies={"http": None, "https": None}
            )
            if response.status_code == 200:
                return self._clean_result(response.json().get("response", ""))
            print(f"Ollama error: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("Ollama not running, translation failed")
        except Exception as e:
            print(f"Translation error: {e}")
        return ""

    def translate_batch(self, texts):
        """Translate a short ordered batch, returning one result per input."""
        texts = [text.strip() for text in texts if text and text.strip()]
        if not texts:
            return []
        if len(texts) == 1:
            return [self.translate(texts[0])]

        numbered = "\n".join(f"[{index}] {text}" for index, text in enumerate(texts, 1))
        prompt = (
            "Translate each Japanese line to Simplified Chinese. "
            "Return exactly one line per input, preserving the [number] prefix. "
            "Output ONLY the numbered translations.\n\n" + numbered
        )
        try:
            response = requests.post(
                "http://127.0.0.1:11434/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.1, "num_ctx": 2048}},
                timeout=30, proxies={"http": None, "https": None}
            )
            if response.status_code == 200:
                parsed = {}
                for line in response.json().get("response", "").splitlines():
                    line = line.strip()
                    if line.startswith("[") and "]" in line:
                        number, value = line.split("]", 1)
                        if number[1:].isdigit():
                            parsed[int(number[1:])] = self._clean_result(value)
                if len(parsed) == len(texts) and all(parsed.get(i) for i in range(1, len(texts) + 1)):
                    return [parsed[i] for i in range(1, len(texts) + 1)]
                print("Batch translation returned incomplete numbered output; falling back")
            else:
                print(f"Ollama batch error: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("Ollama not running, batch translation failed")
        except Exception as e:
            print(f"Batch translation error: {e}")

        return [self.translate(text) for text in texts]
