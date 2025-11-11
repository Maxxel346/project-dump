--
-- PostgreSQL database dump
--

-- Dumped from database version 17.0
-- Dumped by pg_dump version 17.4

-- Started on 2025-11-11 16:32:29

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 2 (class 3079 OID 24581)
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- TOC entry 3558 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- TOC entry 261 (class 1255 OID 24662)
-- Name: normalize_search_tags(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.normalize_search_tags() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Sort include_tags_json by tag id (the 2nd element of each pair)
    NEW.include_tags_json := (
        SELECT jsonb_agg(elem ORDER BY (elem->>1)::int)
        FROM jsonb_array_elements(COALESCE(NEW.include_tags_json, '[]'::jsonb)) elem
    );

    -- Sort exclude_tags_json similarly
    NEW.exclude_tags_json := (
        SELECT jsonb_agg(elem ORDER BY (elem->>1)::int)
        FROM jsonb_array_elements(COALESCE(NEW.exclude_tags_json, '[]'::jsonb)) elem
    );

    RETURN NEW;
END;
$$;


ALTER FUNCTION public.normalize_search_tags() OWNER TO postgres;

--
-- TOC entry 262 (class 1255 OID 24663)
-- Name: update_tag_count(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_tag_count() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE tags SET count = count + 1 WHERE id = NEW.tag_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE tags SET count = count - 1 WHERE id = OLD.tag_id;
    END IF;
    RETURN NULL;
END;
$$;


ALTER FUNCTION public.update_tag_count() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 218 (class 1259 OID 24664)
-- Name: failed_tasks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.failed_tasks (
    id bigint NOT NULL,
    reason text,
    retries integer,
    last_error text,
    failed_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.failed_tasks OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 24670)
-- Name: favorite_media; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.favorite_media (
    id integer NOT NULL,
    media_id bigint NOT NULL,
    created timestamp without time zone DEFAULT now()
);


ALTER TABLE public.favorite_media OWNER TO postgres;

--
-- TOC entry 220 (class 1259 OID 24674)
-- Name: favorite_media_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.favorite_media_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.favorite_media_id_seq OWNER TO postgres;

--
-- TOC entry 3559 (class 0 OID 0)
-- Dependencies: 220
-- Name: favorite_media_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.favorite_media_id_seq OWNED BY public.favorite_media.id;


--
-- TOC entry 221 (class 1259 OID 24675)
-- Name: favorite_tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.favorite_tags (
    id integer NOT NULL,
    tag_id bigint NOT NULL,
    tag_value text NOT NULL,
    created timestamp without time zone DEFAULT now()
);


ALTER TABLE public.favorite_tags OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 24681)
-- Name: favorite_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.favorite_tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.favorite_tags_id_seq OWNER TO postgres;

--
-- TOC entry 3560 (class 0 OID 0)
-- Dependencies: 222
-- Name: favorite_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.favorite_tags_id_seq OWNED BY public.favorite_tags.id;


--
-- TOC entry 223 (class 1259 OID 24682)
-- Name: media; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.media (
    id bigint NOT NULL,
    created timestamp without time zone,
    posted timestamp without time zone,
    likes integer,
    type integer,
    status integer,
    uploader_id bigint,
    width integer,
    height integer
);


ALTER TABLE public.media OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 24685)
-- Name: media_sources; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.media_sources (
    id integer NOT NULL,
    media_id bigint,
    source text
);


ALTER TABLE public.media_sources OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 24690)
-- Name: media_sources_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.media_sources_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.media_sources_id_seq OWNER TO postgres;

--
-- TOC entry 3561 (class 0 OID 0)
-- Dependencies: 225
-- Name: media_sources_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.media_sources_id_seq OWNED BY public.media_sources.id;


--
-- TOC entry 226 (class 1259 OID 24691)
-- Name: media_tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.media_tags (
    media_id bigint NOT NULL,
    tag_id bigint NOT NULL
);


ALTER TABLE public.media_tags OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 24694)
-- Name: search_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.search_history (
    id bigint NOT NULL,
    user_id bigint,
    include_tags text[] DEFAULT '{}'::text[] NOT NULL,
    exclude_tags text[] DEFAULT '{}'::text[] NOT NULL,
    favorite_only boolean DEFAULT false NOT NULL,
    created timestamp without time zone DEFAULT now() NOT NULL,
    include_tags_json jsonb DEFAULT '[]'::jsonb NOT NULL,
    exclude_tags_json jsonb DEFAULT '[]'::jsonb NOT NULL
);


ALTER TABLE public.search_history OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 24705)
-- Name: search_history_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.search_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.search_history_id_seq OWNER TO postgres;

--
-- TOC entry 3562 (class 0 OID 0)
-- Dependencies: 228
-- Name: search_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.search_history_id_seq OWNED BY public.search_history.id;


--
-- TOC entry 229 (class 1259 OID 24706)
-- Name: tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tags (
    id bigint NOT NULL,
    value text NOT NULL,
    type integer,
    popularity integer,
    count integer
);


ALTER TABLE public.tags OWNER TO postgres;

--
-- TOC entry 3365 (class 2604 OID 24711)
-- Name: favorite_media id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.favorite_media ALTER COLUMN id SET DEFAULT nextval('public.favorite_media_id_seq'::regclass);


--
-- TOC entry 3367 (class 2604 OID 24712)
-- Name: favorite_tags id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.favorite_tags ALTER COLUMN id SET DEFAULT nextval('public.favorite_tags_id_seq'::regclass);


--
-- TOC entry 3369 (class 2604 OID 24713)
-- Name: media_sources id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media_sources ALTER COLUMN id SET DEFAULT nextval('public.media_sources_id_seq'::regclass);


--
-- TOC entry 3370 (class 2604 OID 24714)
-- Name: search_history id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.search_history ALTER COLUMN id SET DEFAULT nextval('public.search_history_id_seq'::regclass);


--
-- TOC entry 3378 (class 2606 OID 24894)
-- Name: failed_tasks failed_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.failed_tasks
    ADD CONSTRAINT failed_tasks_pkey PRIMARY KEY (id);


--
-- TOC entry 3380 (class 2606 OID 24896)
-- Name: favorite_media favorite_media_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.favorite_media
    ADD CONSTRAINT favorite_media_pkey PRIMARY KEY (id);


--
-- TOC entry 3382 (class 2606 OID 24898)
-- Name: favorite_tags favorite_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.favorite_tags
    ADD CONSTRAINT favorite_tags_pkey PRIMARY KEY (id);


--
-- TOC entry 3386 (class 2606 OID 24900)
-- Name: media media_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_pkey PRIMARY KEY (id);


--
-- TOC entry 3388 (class 2606 OID 24902)
-- Name: media_sources media_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media_sources
    ADD CONSTRAINT media_sources_pkey PRIMARY KEY (id);


--
-- TOC entry 3393 (class 2606 OID 24904)
-- Name: media_tags media_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media_tags
    ADD CONSTRAINT media_tags_pkey PRIMARY KEY (media_id, tag_id);


--
-- TOC entry 3395 (class 2606 OID 24912)
-- Name: search_history search_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.search_history
    ADD CONSTRAINT search_history_pkey PRIMARY KEY (id);


--
-- TOC entry 3401 (class 2606 OID 24914)
-- Name: tags tags_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);


--
-- TOC entry 3383 (class 1259 OID 24915)
-- Name: idx_media_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_media_created ON public.media USING btree (created DESC);


--
-- TOC entry 3384 (class 1259 OID 24916)
-- Name: idx_media_created_desc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_media_created_desc ON public.media USING btree (created DESC);


--
-- TOC entry 3389 (class 1259 OID 24917)
-- Name: idx_media_tags_media_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_media_tags_media_id ON public.media_tags USING btree (media_id);


--
-- TOC entry 3390 (class 1259 OID 24918)
-- Name: idx_media_tags_media_tag; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX idx_media_tags_media_tag ON public.media_tags USING btree (media_id, tag_id);


--
-- TOC entry 3391 (class 1259 OID 24919)
-- Name: idx_media_tags_tag_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_media_tags_tag_id ON public.media_tags USING btree (tag_id);


--
-- TOC entry 3397 (class 1259 OID 24920)
-- Name: idx_tags_popularity; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_tags_popularity ON public.tags USING btree (popularity DESC);


--
-- TOC entry 3398 (class 1259 OID 24921)
-- Name: idx_tags_value; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_tags_value ON public.tags USING btree (value);


--
-- TOC entry 3399 (class 1259 OID 24922)
-- Name: idx_tags_value_trgm; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_tags_value_trgm ON public.tags USING gin (value public.gin_trgm_ops);


--
-- TOC entry 3402 (class 1259 OID 24923)
-- Name: tags_value_trgm_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX tags_value_trgm_idx ON public.tags USING gin (value public.gin_trgm_ops);


--
-- TOC entry 3396 (class 1259 OID 65556)
-- Name: unique_search_history_hash; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX unique_search_history_hash ON public.search_history USING btree (user_id, md5((include_tags_json)::text), md5((exclude_tags_json)::text));


--
-- TOC entry 3407 (class 2620 OID 24925)
-- Name: search_history trg_normalize_search_tags; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_normalize_search_tags BEFORE INSERT OR UPDATE ON public.search_history FOR EACH ROW EXECUTE FUNCTION public.normalize_search_tags();


--
-- TOC entry 3406 (class 2620 OID 24926)
-- Name: media_tags trg_update_tag_count; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_update_tag_count AFTER INSERT OR DELETE ON public.media_tags FOR EACH ROW EXECUTE FUNCTION public.update_tag_count();


--
-- TOC entry 3403 (class 2606 OID 24927)
-- Name: media_sources media_sources_media_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media_sources
    ADD CONSTRAINT media_sources_media_id_fkey FOREIGN KEY (media_id) REFERENCES public.media(id) ON DELETE CASCADE;


--
-- TOC entry 3404 (class 2606 OID 24932)
-- Name: media_tags media_tags_media_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media_tags
    ADD CONSTRAINT media_tags_media_id_fkey FOREIGN KEY (media_id) REFERENCES public.media(id) ON DELETE CASCADE;


--
-- TOC entry 3405 (class 2606 OID 24937)
-- Name: media_tags media_tags_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media_tags
    ADD CONSTRAINT media_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(id) ON DELETE CASCADE;


-- Completed on 2025-11-11 16:32:30

--
-- PostgreSQL database dump complete
--

