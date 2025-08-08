from dataclasses import dataclass
from typing import Optional, List
from azure.search.documents.indexes.models import _edm as EDM
from azure.search.documents.models import VectorQuery, VectorizedQuery
from teams.ai.embeddings import AzureOpenAIEmbeddings, AzureOpenAIEmbeddingsOptions
from teams.state.memory import Memory
from teams.state.state import TurnContext
from teams.ai.tokenizers import Tokenizer
from teams.ai.data_sources import DataSource

from config import Config

# 移除 get_embedding_vector 函數，因為不再使用向量搜尋

@dataclass
class Doc:
    docId: Optional[str] = None
    name: Optional[str] = None  # 改為對應新的欄位結構
    column: Optional[str] = None
    full_description: Optional[str] = None
    tags: Optional[str] = None
    type: Optional[str] = None

@dataclass
class AzureAISearchDataSourceOptions:
    name: str
    indexName: str
    azureAISearchApiKey: str
    azureAISearchEndpoint: str

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import json

@dataclass
class Result:
    def __init__(self, output, length, too_long):
        self.output = output
        self.length = length
        self.too_long = too_long

class AzureAISearchDataSource(DataSource):
    def __init__(self, options: AzureAISearchDataSourceOptions):
        self.name = options.name
        self.options = options
        self.searchClient = SearchClient(
            options.azureAISearchEndpoint,
            options.indexName,
            AzureKeyCredential(options.azureAISearchApiKey)
        )
        
    def name(self):
        return self.name

    async def render_data(self, _context: TurnContext, memory: Memory, tokenizer: Tokenizer, maxTokens: int):
        query = memory.get('temp.input')

        if not query:
            return Result('', 0, False)

        # 使用與第一個範例相同的欄位選擇
        selectedFields = [
            'name',
            'column', 
            'full_description',
            'tags',
            'type'
        ]

        # 使用文字搜尋取代向量搜尋，並加入篩選條件優先搜尋 iv 和 rv 類型
        search_options = {
            "select": selectedFields,
            "filter": "type eq 'iv' or type eq 'rv'",  # 優先搜尋 iv 和 rv 類型
            "top": 5,  # 限制返回結果數量
            "include_total_count": True,
            "scoring_profile": "custom_scoring"  # 使用自定義評分策略
        }

        try:
            searchResults = self.searchClient.search(
                search_text=query,
                **search_options
            )
        except Exception as e:
            # 如果使用篩選條件失敗（可能是因為索引沒有 custom_scoring），則使用基本搜尋
            basic_search_options = {
                "select": selectedFields,
                "top": 5
            }
            searchResults = self.searchClient.search(
                search_text=query,
                **basic_search_options
            )

        if not searchResults:
            return Result('', 0, False)

        usedTokens = 0
        doc_list = []
        
        # 格式化搜尋結果，與第一個範例保持一致
        for result in searchResults:
            # 建構結構化的文件資訊
            formatted_result = {
                "name": result.get("name", ""),
                "type": result.get("type", ""),
                "column": result.get("column", ""),
                "description": result.get("full_description", ""),
                "tags": result.get("tags", ""),
                "score": result.get("@search.score", 0)  # 包含相關性得分
            }
            
            # 計算 token 使用量
            result_text = json.dumps(formatted_result, ensure_ascii=False)
            tokens = len(tokenizer.encode(result_text))

            if usedTokens + tokens > maxTokens:
                break

            doc_list.append(formatted_result)
            usedTokens += tokens

        # 將所有結果合併為單一文件字串
        final_doc = json.dumps(doc_list, ensure_ascii=False, indent=2)
        
        return Result(final_doc, usedTokens, usedTokens > maxTokens)