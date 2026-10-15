"""Prompt templates for fact extraction and method-blind support judgments (verbatim from the paper, Appendix A)."""
import json

EXTRACT_PROMPT = """You are building an information inventory for a group of documents that a deduplication pipeline put together.
They may be versions of the same story, or different pages that only share a template.

List the atomic facts contained in the UNION of all documents below. Rules:
- One fact = one checkable claim (who/what/when/where/how many/quote attribution), self-contained, at most 30 words, with names spelled out (no pronouns).
- State the claim itself. NEVER mention documents, versions, pages or their letters (write "Haqqani was 72", not "Document B says Haqqani was 72").
- Cover every distinct piece of information, including details that appear in only ONE document (e.g. a reporter credit, an added quote, an updated number, a product price).
- If documents disagree (e.g. age 72 vs 71, 3 dead vs 5 dead), write each variant as its own separate fact.
- Do not list facts implied only by world knowledge. Skip pure boilerplate (navigation menus, cookie notices, copyright lines).
- Between 8 and 45 facts. Prefer informative facts over trivial wording.

Return JSON only: {{"facts": ["fact 1", "fact 2", ...]}}

{docs}"""

JUDGE_PROMPT = """For each FACT and each DOCUMENT below, decide whether the document conveys the fact.
Labels:
- "S": the document states the fact or clearly entails it (paraphrase is fine).
- "C": the document contradicts it (gives a different value for the same thing, e.g. a different number, date, or name).
- "N": the document does not mention it.
Judge each document independently, using only its own text.

Return JSON only: {{"labels": {{"F1": {{"A": "S", "B": "N", ...}}, "F2": {{...}}, ...}}}} covering every fact and every document letter.

FACTS:
{facts}

{docs}"""

FACT_TYPES = ["number_date", "relation", "event", "quotation", "credit", "commercial", "template", "other"]

FACT_TYPE_PROMPT = '''Assign exactly one primary type per atomic fact, applying the following priority when categories overlap:
template: navigation, cookie/copyright text, generic site boilerplate with no substantive claim;
credit: reporter/byline/contributor/photo/source production credits (not substantive quoted statements);
commercial: product/service price, purchase/sales/contact details or business offers;
quotation: quoted speech/opinion or substantive statement attributed to a speaker/source;
number_date: the central checkable claim is a quantity, measurement, age, date, or time;
relation: a person's or organization's identity, role, affiliation, kinship or relationship;
event: a substantive action, occurrence, process or outcome not classified above;
other: remaining substantive attributes or claims.
Use only the fact text, no world knowledge. Category names must exactly match the names above.
Return JSON only: {"items":[{"id":"input id","type":"category"}, ...]} in the original order.
FACTS:\n'''


def letters(n):
    return [chr(65 + i) for i in range(n)]


def docs_block(versions, labels):
    return "\n\n".join(f"=== DOCUMENT {lab} ===\nTITLE: {v['title']}\n{v['text']}" for lab, v in zip(labels, versions))


def parse_json(text):
    """Return the first JSON object in a model response, tolerating surrounding prose or code fences."""
    dec = json.JSONDecoder()
    for key in ('{"facts"', '{"labels"', '{"items"', "{"):
        i = text.find(key)
        while i != -1:
            try:
                return dec.raw_decode(text[i:])[0]
            except json.JSONDecodeError:
                i = text.find(key, i + 1)
    raise json.JSONDecodeError("no JSON object found", text[:200], 0)
