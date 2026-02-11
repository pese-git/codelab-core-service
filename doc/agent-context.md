# ТЕХНИЧЕСКОЕ ЗАДАНИЕ  
## Personal Multi-Agent AI Platform - АГЕНТНЫЙ КОНТЕКСТ  
**Версия 5.1** | **11 февраля 2026**

***

## 1. 🔄 НОВОЕ ТРЕБОВАНИЕ: АГЕНТНЫЙ КОНТЕКСТ

**Ключевые изменения v1.0:**
```
НЕ user123_context (общий)
А ТОЧНО: user123_researcher_context, user123_coder_context...

Каждый агент имеет СВОЮ изолированную память!
```

***

## 2. 🗄️ НОВАЯ СТРУКТУРА QDRANT

```
QDRANT Collections (per agent):
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│ user123_researcher  │ │ user123_coder       │ │ user123_writer      │
│ ├─ vectors[1M+]     │ │ ├─ vectors[500K+]   │ │ ├─ vectors[300K+]   │
│ ├─ RAG search       │ │ ├─ code examples    │ │ ├─ writing style    │
│ └─ research history │ │ └─ coding patterns  │ │ └─ user preferences │
└─────────────────────┘ └─────────────────────┘ └─────────────────────┘
```

### 2.1. AgentContext Schema

```python
# vectorstore/agent_context.py
class AgentContext:
    """Изолированный контекст конкретного агента"""
    
    def __init__(self, agent_id: str, qdrant_client):
        self.agent_id = agent_id
        self.collection_name = agent_id + "_context"  # user123_coder_context
        self.client = qdrant_client
        self._ensure_collection()
    
    async def store_interaction(self, interaction: AgentInteraction):
        """Сохраняет взаимодействие агента"""
        embedding = await generate_embedding(interaction.content)
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[PointStruct(
                id=UUID(interaction.id),
                vector=embedding,
                payload={
                    "agent_id": self.agent_id,
                    "user_id": extract_user_id(self.agent_id),
                    "interaction_type": interaction.type,  # task, tool, direct_call
                    "timestamp": interaction.timestamp,
                    "task_id": interaction.task_id or None,
                    "success": interaction.success,
                    "content_type": classify_content(interaction.content)
                }
            )]
        )
    
    async def retrieve_context(self, query: str, limit: int = 8) -> List[ContextChunk]:
        """RAG для агента - только его контекст"""
        query_embedding = await generate_embedding(query)
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            score_threshold=0.75,  # Высокая релевантность
            query_filter=Filter(  # Только успешные взаимодействия
                must=[
                    FieldCondition(key="success", match=MatchValue(value=True)),
                    FieldCondition(key="agent_id", match=MatchValue(value=self.agent_id))
                ]
            )
        )
        
        return [AgentContextChunk.from_qdrant(hit) for hit in results]
```

***

## 3. 🤖 АГЕНТ С ЛИЧНЫМ КОНТЕКСТОМ

```python
# agents/contextual_agent.py
class ContextualAgent(BaseAgent):
    """Агент с персональным контекстом"""
    
    def __init__(self, agent_config: dict, agent_context: AgentContext):
        super().__init__(agent_config)
        self.context_store = agent_context  # СВОЙ Qdrant!
    
    async def execute_task(self, task_data: dict, session_id: int):
        """Задача с учетом ЛИЧНОГО контекста агента"""
        
        # 1. Ищем в СВОЕМ контексте
        relevant_context = await self.context_store.retrieve_context(
            query=task_data['description']
        )
        
        # 2. Строим персонализированный промпт
        memory_prompt = self._build_agent_memory_prompt(relevant_context)
        
        full_prompt = f"""
        ТВОЯ ПАМЯТЬ ({len(relevant_context)} примеров):
        {memory_prompt}
        
        НОВАЯ ЗАДАЧА: {task_data['description']}
        
        Используй опыт из памяти, но адаптируй под новую задачу.
        """
        
        # 3. Выполняем
        response = await self.llm.chat([{"role": "user", "content": full_prompt}])
        
        # 4. Сохраняем в СВОЙ контекст
        await self.context_store.store_interaction(AgentInteraction(
            content=response.content,
            type="task_response",
            task_id=task_data['task_id'],
            success=True
        ))
        
        return response
```

***

## 4. 🏗️ ИНИЦИАЛИЗАЦИЯ АГЕНТНЫХ КОНТЕКСТОВ

```python
# workers/user_space.py (обновлено)
class UserWorkerSpace:
    
    async def _load_agents(self, db: AsyncSession):
        """Загружает агентов СВОИМИ контекстами"""
        agents = await db.execute(
            select(UserAgent).where(UserAgent.user_id == self.user_id)
        )
        
        for agent_record in agents.scalars():
            agent_context = AgentContext(agent_record.agent_id, self.qdrant_client)
            
            self.agent_cache[agent_record.agent_id] = ContextualAgent(
                agent_record.config,
                agent_context  # ← КАЖДЫЙ со своим!
            )
```

***

## 5. 🔍 SPEZIALIZIROVANNYE RAG ПОИСКИ

### 5.1. Кодер ищет кодовые примеры

```python
# agent_id=user123_coder
coder_context.retrieve_context("FastAPI CRUD", filters={
    "content_type": "code_snippet",
    "language": "python"
})
```

### 5.2. Researcher ищет исследования

```python
# agent_id=user123_researcher  
researcher_context.retrieve_context("React hooks", filters={
    "content_type": "research",
    "source": "web_search"
})
```

***

## 6. 📊 АГЕНТНЫЕ МЕТРИКИ КОНТЕКСТА

```
Контекст per agent:
user123_coder_context: 847K vectors (code patterns)
user123_researcher_context: 1.2M vectors (research)
user123_writer_context: 342K vectors (style)

Метрики:
agent_context_recall{agent="user123_coder"} = 0.92
agent_context_search_latency = 38ms
agent_memory_usage_mb = 245MB
```

***

## 7. 🎨 UI: АГЕНТНЫЕ ПРОФИЛИ

```
👤 Мои агенты:

🔧 @coder (1.2M памяти)
├─ Специализация: Python, FastAPI
├─ Последние задачи: API, validators
└─ [🧹 Очистить память]

🔬 @researcher (2.1M памяти)  
├─ Специализация: Web, React docs
└─ [📊 Статистика памяти]

✍️ @writer (450K памяти)
└─ Стиль: Техническая документация
```

### 7.1. Управление памятью агента

```
POST /my/agents/user123_coder/context/
{
  "action": "clear",     // Очистить память
  "filter": "old_tasks"  // или по фильтру
}
```

***

## 8. 🧹 MEMORY MANAGEMENT API

```python
@app.post("/my/agents/{agent_id}/context/")
async def manage_agent_memory(
    agent_id: str,
    action: str,  # clear, prune, export
    user_space: UserWorkerSpace = Depends(get_user_space)
):
    agent_context = user_space.agent_contexts[agent_id]
    
    if action == "clear":
        await agent_context.clear()
        return {"deleted": "all"}
    
    elif action == "prune":
        # Удаляем старые/плохие векторы
        await agent_context.prune(days=30, min_score=0.5)
        return {"pruned": 1247}
```

***

## 9. 🔄 КОНТЕКСТ В DIRECT CALLS

```
Direct call @coder "email validator":
1. coder_context.retrieve_context("email validator") → Находит прошлые примеры
2. Строит промпт с прошлыми валидаторами
3. Генерирует новый код на основе опыта
4. Сохраняет в coder_context (не смешивает с researcher)
```

***

## 10. 🎯 ПРЕИМУЩЕСТВА АГЕНТНОГО КОНТЕКСТА

```
✅ SPEZIALIZATION - coder помнит код, researcher - исследования
✅ NO CONTEXT POLLUTION - контексты не смешиваются  
✅ BETTER RAG - каждый агент оптимизирован под свою задачу
✅ MEMORY CONTROL - очистка/экспорт per agent
✅ USER UNDERSTANDING - видит статистику памяти агента
✅ SCALABLE - 1M+ векторов на агента
```

***

## 11. 📈 QDRANT СТРУКТУРА v1.0

```
Collections (per user ~5 agents):
user123_coder_context      → code, patterns
user123_researcher_context → articles, findings  
user123_writer_context     → style, preferences
user123_tester_context     → test cases

Total: ~5M vectors per active user
```

***

## 12. 🛠️ МИГРАЦИЯ ИЗ v5.0

```python
async def migrate_to_agent_contexts(user_id: int):
    """Разделяем user{user_id}_context → agent-specific"""
    
    user_collection = f"user{user_id}_context"
    agents = await get_user_agents(user_id)
    
    for agent in agents:
        agent_collection = f"{agent.agent_id}_context"
        
        # Переносим сообщения этого агента
        agent_docs = qdrant.search(
            user_collection,
            query_filter={"agent_id": agent.agent_id}
        )
        
        qdrant.upsert(agent_collection, agent_docs)
    
    # Удаляем общую коллекцию
    qdrant.delete_collection(user_collection)
```

***

## 13. ✅ ИЗМЕНЕНИЯ v1.0

```
✅ ✅ КАЖДЫЙ АГЕНТ - СВОЙ QDRANT КОНТЕКСТ
✅ ✅ Специализированная память (code/research/writing)
✅ ✅ Контекст не смешивается между агентами
✅ ✅ UI управление памятью per agent
✅ ✅ Метрики и статистика памяти агента
✅ ✅ Прямые вызовы используют личный контекст
✅ ✅ Масштабируется до 1M+ векторов на агента
```

**Теперь каждый агент - эксперт в своей области с персональной памятью!** 🧠🤖✨

***

**Техническое задание обновлено. Версия 5.1 утверждена.**