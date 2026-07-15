```mermaid
graph TD
    %% 스타일 정의
    classDef source fill:#f9f,stroke:#333,stroke-width:2px;
    classDef process fill:#bbf,stroke:#333,stroke-width:2px;
    classDef ui fill:#dfd,stroke:#333,stroke-width:2px;
    classDef ai fill:#fdd,stroke:#333,stroke-width:2px;

    %% 노드 정의
    A[기업마당 OpenAPI]:::source -->|Raw Data JSON| B(Python 필터링 엔진):::process
    
    subgraph Data Pipeline [데이터 가공 및 필터링]
        B --> B1["하드 필터링 (IS_PAPER_RELATED)"]
        B --> B2["스마트 지역 매핑 (APPLY_REGION)"]
    end
    
    B1 & B2 -->|Refined Data Frame| C(Streamlit UI 대시보드):::ui
    
    subgraph AI & Interaction [추천 및 대화 엔진]
        C -->|Context & Profile Info| D[Gemini Pro API]:::ai
        D -->|Context-Aware (RAG) Answer| C
    end
    
    C -->|st.session_state| E[즐겨찾기 폴더링 & UI 상태 관리]:::ui
    C -->|openpyxl| F[현업 보고용 Excel 다운로드]:::process
