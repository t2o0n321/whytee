-- Supabase / PostgreSQL schema for the YouTube channel-analysis architecture.
-- Provides relational tables (channel + video metadata, transcripts, Telegram
-- chat history) and a pgvector embeddings table + cosine-similarity match
-- function used by the n8n Supabase Vector Store node (RAG retrieval).
--
-- Apply with:  psql "$SUPABASE_DB_URL" -f supabase/schema.sql

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- Channels & videos (relational metadata)
-- ---------------------------------------------------------------------------
create table if not exists channels (
    id              text primary key,          -- YouTube channel id
    title           text,
    created_at      timestamptz not null default now()
);

create table if not exists videos (
    id              text primary key,          -- 11-char video id
    channel_id      text references channels(id) on delete cascade,
    title           text,
    published_at    timestamptz,
    duration_s      double precision,
    view_count      bigint,
    -- state flags mirror YTScribe's stateful CSV tracker (resumable backfill)
    transcript_done boolean not null default false,
    analysis_done   boolean not null default false,
    created_at      timestamptz not null default now()
);

create index if not exists videos_channel_idx on videos(channel_id);

-- ---------------------------------------------------------------------------
-- Raw transcripts (one row per video)
-- ---------------------------------------------------------------------------
create table if not exists transcripts (
    video_id        text primary key references videos(id) on delete cascade,
    language        text,
    source          text,                      -- captions | whisper_local
    full_text       text,
    segments        jsonb,                     -- [{start,duration,text}, ...]
    created_at      timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Vector store for RAG (chunked transcript embeddings)
-- 1536 dims matches OpenAI-compatible small embedding models via OpenRouter.
-- ---------------------------------------------------------------------------
create table if not exists embeddings (
    id              bigserial primary key,
    video_id        text references videos(id) on delete cascade,
    content         text not null,             -- the chunk text
    metadata        jsonb not null default '{}'::jsonb,
    embedding       vector(1536)
);

-- IVFFlat index for cosine similarity. Tune `lists` to your corpus size.
create index if not exists embeddings_vector_idx
    on embeddings using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

-- ---------------------------------------------------------------------------
-- Telegram conversation memory (Agentic RAG chat, workflow 04)
--
-- Column layout matches what n8n's "Postgres Chat Memory"
-- (@n8n/n8n-nodes-langchain.memoryPostgresChat) node expects: a serial id, a
-- text session_id (the Telegram chat id), and the serialized LangChain message
-- as JSONB. Do NOT add NOT NULL columns the node won't populate, or writes fail.
-- ---------------------------------------------------------------------------
create table if not exists n8n_chat_histories (
    id              serial primary key,
    session_id      varchar(255) not null,     -- Telegram chat id
    message         jsonb not null,            -- {"type": "...", "data": {...}}
    created_at      timestamptz not null default now()
);

create index if not exists n8n_chat_histories_session_idx
    on n8n_chat_histories(session_id);

-- ---------------------------------------------------------------------------
-- Cosine-similarity retrieval used by n8n's Supabase Vector Store node.
-- ---------------------------------------------------------------------------
create or replace function match_documents (
    query_embedding vector(1536),
    match_count int default 5,
    filter jsonb default '{}'::jsonb
)
returns table (
    id bigint,
    video_id text,
    content text,
    metadata jsonb,
    similarity float
)
language plpgsql
as $$
begin
    return query
    select
        e.id,
        e.video_id,
        e.content,
        e.metadata,
        1 - (e.embedding <=> query_embedding) as similarity
    from embeddings e
    where e.metadata @> filter
    order by e.embedding <=> query_embedding
    limit match_count;
end;
$$;
