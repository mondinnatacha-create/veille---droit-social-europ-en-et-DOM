"""Workflow de veille hebdomadaire en droit du travail et droit social.

Le workflow collecte les nouveautes depuis des sources officielles (flux RSS et
pages HTML), synthetise un rapport Markdown avec un modele Mistral, puis publie
le rapport dans une bibliotheque de documents Mistral.
"""

from __future__ import annotations

import html as html_module
import io
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx
from pydantic import BaseModel

import mistralai.workflows as workflows
from worker import config


MAX_EXCERPT_CHARS = 400
MAX_ITEMS_FOR_LLM = 60
HTTP_TIMEOUT_SECONDS = 25.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


class VeilleInput(BaseModel):
    lookback_days: int = 7
    library_id: str | None = None
    dry_run: bool = False


class VeilleItem(BaseModel):
    source: str
    title: str
    url: str
    published: str | None = None
    excerpt: str | None = None


class SourceOutcome(BaseModel):
    name: str
    ok: bool = False
    error: str | None = None
    items: list[VeilleItem] = []


class VeilleOutput(BaseModel):
    report_markdown: str
    document_id: str | None = None
    items_collected: int = 0
    sources_ok: int = 0
    sources_total: int = 0


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = html_module.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    return text[:MAX_EXCERPT_CHARS]


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(raw.replace("+00:00", "Z"), fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _matches_keywords(item_title: str | None, excerpt: str | None, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{item_title or ''} {excerpt or ''}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def _parse_feed(xml_text: str) -> list[tuple[str | None, str | None, str | None, str | None]]:
    entries: list[tuple[str | None, str | None, str | None, str | None]] = []
    root = ET.fromstring(xml_text)
    for item in root.iter():
        tag = item.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        title = link = published = summary = None
        for child in item:
            child_tag = child.tag.rsplit("}", 1)[-1]
            if child_tag == "title":
                title = _clean_text(child.text)
            elif child_tag == "link":
                link = (child.text or "").strip() or child.attrib.get("href")
            elif child_tag in ("pubDate", "published", "updated", "date"):
                published = published or (child.text or "").strip()
            elif child_tag in ("description", "summary", "content"):
                summary = summary or _clean_text(child.text)
        if title:
            entries.append((title, link, published, summary))
    return entries


_LINK_RE = re.compile(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', re.DOTALL)
_DATE_RE = re.compile(r"(\d{1,2})\s+(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\s+(\d{4})", re.IGNORECASE)
_MONTHS_FR = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}


def _parse_html_links(
    page_text: str, base_url: str, link_pattern: str | None = None
) -> list[tuple[str | None, str | None, str | None, str | None]]:
    entries: list[tuple[str | None, str | None, str | None, str | None]] = []
    seen: set[str] = set()
    prev_end = 0
    for match in _LINK_RE.finditer(page_text):
        href, text = match.group(1), match.group(2)
        title = _clean_text(text)
        if not title or href in seen or href.startswith(("mailto:", "javascript:")):
            continue
        if link_pattern and not re.search(link_pattern, href):
            continue
        seen.add(href)
        url = href if href.startswith("http") else httpx.URL(base_url).join(href)
        window = page_text[prev_end:match.start()]
        prev_end = match.end()
        date_match = _DATE_RE.search(window)
        published = None
        if date_match:
            day, month_name, year = date_match.groups()
            month = _MONTHS_FR.get(month_name.lower())
            if month:
                published = f"{year}-{month:02d}-{int(day):02d}"
        entries.append((title, str(url), published, None))
    return entries


@workflows.activity()
async def collect_sources(lookback_days: int) -> list[SourceOutcome]:
    """Collecte les nouveautes de chaque source officielle, sans jamais echouer globalement."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    outcomes: list[SourceOutcome] = []
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as http:
        for source in config.SOURCES:
            outcome = SourceOutcome(name=source["name"])
            try:
                response = await http.get(source["url"])
                response.raise_for_status()
                body = response.text
                if source["kind"] == "rss":
                    raw_entries = _parse_feed(body)
                else:
                    raw_entries = _parse_html_links(body, source["url"], source.get("link_pattern"))
                keywords = source.get("keywords") or []
                kept = 0
                for title, link, published, summary in raw_entries:
                    if kept >= source.get("max_items", 12):
                        break
                    if not _matches_keywords(title, summary, keywords):
                        continue
                    parsed_date = _parse_date(published)
                    if parsed_date is not None and parsed_date < cutoff:
                        continue
                    outcome.items.append(
                        VeilleItem(
                            source=source["name"],
                            title=title or "(sans titre)",
                            url=link or source["url"],
                            published=published,
                            excerpt=summary,
                        )
                    )
                    kept += 1
                outcome.ok = True
            except Exception as exc:
                outcome.ok = False
                outcome.error = f"{type(exc).__name__}: {exc}"[:300]
            outcomes.append(outcome)
    return outcomes


@workflows.activity()
async def synthesize_report(outcomes: list[SourceOutcome], lookback_days: int) -> str:
    """Synthetise les elements collectes en un rapport Markdown, uniquement a partir des donnees collectees."""
    from mistralai.workflows.client import get_mistral_client

    items = [item for outcome in outcomes for item in outcome.items]
    failed = [outcome for outcome in outcomes if not outcome.ok]
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=lookback_days)

    if not items:
        return (
            f"# {config.AGENT_TITLE} - rapport du {period_end.strftime('%d/%m/%Y')}\n\n"
            "Aucune nouveaute n'a pu etre collectee pendant la periode "
            f"du {period_start.strftime('%d/%m/%Y')} au {period_end.strftime('%d/%m/%Y')}.\n\n"
            f"Sources consultees : {len(outcomes)}, en echec : {len(failed)}.\n"
        )

    payload = {
        "periode": {
            "debut": period_start.strftime("%d/%m/%Y"),
            "fin": period_end.strftime("%d/%m/%Y"),
        },
        "elements_collectes": [item.model_dump() for item in items[:MAX_ITEMS_FOR_LLM]],
        "sources_en_echec": [
            {"source": outcome.name, "erreur": outcome.error} for outcome in failed
        ],
    }

    system_prompt = (
        "Tu es un juriste specialise en droit du travail et en droit social, redacteur d'une "
        "veille juridique hebdomadaire pour des professionnels (DRH, juristes, avocats, CSE). "
        "Tu rediges en francais, en Markdown, de facon factuelle et sobre. "
        "Tu t'appuies EXCLUSIVEMENT sur les elements collectes fournis dans le message : "
        "n'invente aucun texte, aucune date, aucune reference qui n'y figure pas. "
        "Si un element est sans date, signale-le comme 'date non precisee'. "
        "Termine le rapport par cet avertissement en italique : "
        "'_Rapport genere automatiquement a partir de sources officielles publiques. "
        "Ce document ne constitue pas un avis juridique._'"
    )

    user_prompt = (
        f"Rédige le rapport hebdomadaire '{config.AGENT_TITLE}' couvrant la periode du "
        f"{payload['periode']['debut']} au {payload['periode']['fin']}.\n\n"
        "Structure attendue :\n"
        "# {titre de l'agent} - semaine du {periode}\n\n"
        "## Synthese executif\n(3 a 5 puces : les points les plus importants de la semaine)\n\n"
        "## Textes officiels et reglementaires\n(lois, decrets, ordonnances, circulaires, bulletins officiels)\n\n"
        "## Jurisprudence\n(decisions Cour de cassation, Conseil d'Etat)\n\n"
        "## Cotisations, URSSAF et protection sociale\n\n"
        "## Autres actualites notables\n\n"
        "## Sources indisponibles cette semaine\n(liste simple, ou 'aucune')\n\n"
        "Consignes :\n"
        "- Omet les sections sans contenu pertinent (sauf 'Sources indisponibles').\n"
        "- Pour chaque nouveaute : titre en gras suivie du lien source, source et date, puis "
        "1 a 2 phrases de synthese et, si pertinent, une puce 'Impact : ...' pour les professionnels.\n"
        "- Ne reprends pas les doublons evidents entre sources.\n\n"
        "Donnees collectees (JSON) :\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=1)}"
    )

    client = get_mistral_client()
    response = client.chat.complete(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content
    if isinstance(content, list):
        content = "".join(
            chunk.text for chunk in content if getattr(chunk, "text", None)
        )
    if not content:
        raise RuntimeError("Le modele n'a renvoye aucun contenu pour la synthese.")
    return content


@workflows.activity()
async def publish_report(report_markdown: str, library_id: str | None, dry_run: bool) -> str | None:
    """Publie le rapport Markdown dans la bibliotheque Mistral."""
    if dry_run:
        return None
    from mistralai.workflows.client import get_mistral_client

    resolved_library_id = library_id or os.environ.get("VEILLE_LIBRARY_ID") or config.DEFAULT_LIBRARY_ID
    client = get_mistral_client()
    try:
        from mistralai.client.models import File
    except ImportError:
        from mistralai.models import File

    file_name = f"veille-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
    uploaded = client.beta.libraries.documents.upload(
        library_id=resolved_library_id,
        file=File(fileName=file_name, content=io.BytesIO(report_markdown.encode("utf-8"))),
    )
    return uploaded.id


@workflows.workflow.define(
    name=config.WORKFLOW_NAME,
    workflow_display_name=config.AGENT_TITLE,
    workflow_description=(
        "Veille hebdomadaire : collecte sur les sources officielles, synthese par un modele "
        "Mistral, publication du rapport dans une bibliotheque de documents."
    ),
)
class VeilleWorkflow:
    @workflows.workflow.entrypoint
    async def run(self, input: VeilleInput) -> VeilleOutput:
        outcomes = await collect_sources(input.lookback_days)
        report = await synthesize_report(outcomes, input.lookback_days)
        document_id = await publish_report(report, input.library_id, input.dry_run)
        return VeilleOutput(
            report_markdown=report,
            document_id=document_id,
            items_collected=sum(len(outcome.items) for outcome in outcomes),
            sources_ok=sum(1 for outcome in outcomes if outcome.ok),
            sources_total=len(outcomes),
        )
