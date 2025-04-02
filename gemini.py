import json
import logging
import time
import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting
logger = logging.getLogger(__name__)
class GeminiClient(object):
    model = None
    safety_config = [
        SafetySetting(
            category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        ),
       SafetySetting(
            category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        ),
        SafetySetting(
            category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        ),
        SafetySetting(
            category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        ),
        SafetySetting(
            category=SafetySetting.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
            threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        ),
        SafetySetting(
            category=SafetySetting.HarmCategory.HARM_CATEGORY_UNSPECIFIED,
            threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        ),
    ]
    def __new__(cls):
        if not hasattr(cls, 'instance'):
             cls.instance = super(GeminiClient, cls).__new__(cls)
             cls.instance.initialized = False
        return cls.instance
    
    def __init__(self):
        if self.initialized == True:
            return
        
        vertexai.init(project="three-doors-422720", location="us-west1")
        self.initialized = True
        
    # API Docs: https://cloud.google.com/vertex-ai/generative-ai/docs/reference/python/latest
    def call_model(self, system_instruction, prompt_text) -> str:
        self.model = GenerativeModel("gemini-2.0-flash",
                                 system_instruction=system_instruction,
                                 safety_settings=self.safety_config)
        response = self.model.generate_content(
            prompt_text
            )
        safety = "3"
        for c in response.candidates:
            if str(c.finish_reason) == safety:
                logger.info("Gemini responded with safety flag.")
                return "[EDITOR_FORBIDDEN] LLM safety flagged content."
        return response.text
    
    def call_model_json_out(self, system_instruction, prompt_text) -> str:
        responseText = self.call_model(system_instruction=system_instruction,
                                                            prompt_text=prompt_text)
        if "EDITOR_FORBIDDEN" in responseText:
            return responseText
        
        responseText = responseText.replace('```json', '').replace('```', '')
        return self.sanitize_json(respText=responseText, retryCount=0)
    
    def sanitize_json(self, respText, retryCount) -> str:
        maxRetries = 3
        if retryCount > maxRetries:
            logger.error("failed to sanitize json text")
            return Exception("max retries exceeded for sanitizing json")
        isValidJson = self.parse(respText)
        if isValidJson:
            return respText
        logger.info("Detected invalid json")
        jsonInstruction = """
            The following input is invalid json.
            You will transform the input into valid json, and
            return syntactically correct json.
            ###
        """
        self.model = GenerativeModel("gemini-1.5-flash-001",
                                 system_instruction=jsonInstruction,
                                 safety_settings=self.safety_config)
        response = self.model.generate_content(
            respText
            )
        respText = response.text.replace('```json', '').replace('```', '')
        isValidJson = self.parse(respText)
        if isValidJson:
            return respText
        time.sleep(15)
        return self.sanitize_json(respText=respText, retryCount=retryCount+1)
    
    def parse(self, text) -> bool:
        try:
            json.loads(text)
            return True
        except ValueError as e:
            return False
        
    def analyze_media(self) -> str:
        """
        https://cloud.google.com/vertex-ai/generative-ai/docs/samples/generativeaionvertexai-gemini-pro-example#generativeaionvertexai_gemini_pro_example-python
        """
        # TODO: Implement https://trello.com/c/aADouL3V
        pass