# Hackathon Interne Emerton Data — Sujet #06 : BD Watch + Outreach Drafter

## Contexte
Agent de Business Development : surveille des signaux (presse, LinkedIn, CRM, RH) pour identifier des raisons de contacter un prospect, trouve le bon interlocuteur, et rédige un message personnalisé.

## Équipe
- **Ugo** (Partner Emerton Data) — sponsor, cadrage stratégique, prend les modules HubSpot
- **Franck** (Partner Emerton Data) — absent du cadrage initial (congé)
- **François** (Partner Emerton Strategy) — expertise M&A/Deals/Fonds, à impliquer
- **Loïc** (Senior Consultant) — membre core
- **Benjamin / Ben** (Consultant) — coordination, scraping, point de contact principal
- **Idriss** (Stagiaire) — membre core

---

## Architecture : 2 Piliers

### Pilier A — Prospection Pure
Séquence en 4 étapes :
1. **Captation de triggers** (scraping multi-sources) ← **module en cours de dev**
2. **Scoring via la matrice de ciblage 3D** (fichier de config JSON manuel)
3. **Identification du contact** dans l'org ciblée
4. **Drafting du message** (mail ou LinkedIn, personnalisé)

### Pilier B — Hygiène CRM & Réactivation
- Sources : HubSpot, Gmail, LinkedIn messages, WhatsApp
- Plus pragmatique, moins token-heavy, meilleur taux de conversion
- Converge vers les étapes 3 et 4 du Pilier A
- Ugo prend les modules HubSpot

---

## Module en cours : Captation de Triggers (Étape 1)

### Sources à scraper (par ordre de priorité technique)
| Source | Méthode recommandée | Notes |
|---|---|---|
| Presse FR (Les Echos, La Tribune, LSA...) | RSS feeds → zéro token | Priorité absolue |
| Newsletters Gmail | Gmail connector Cowork | Déjà accessible |
| Communiqués corporate / nominations | RSS (actusnews.com, businesswire.com, AMF) | Rubriques nominations |
| Job openings | Adzuna API ou scraping LinkedIn | Adzuna API disponible |
| M&A / Deals | CFNews, MergerMarket (accès via Franck/Pascal) | Newsletter + filtrage |
| LinkedIn posts | Chrome connector (token-heavy) | Réserver pour step 3 uniquement |

### Mots-clés de veille (Les Echos / presse)
`M&A`, `restructuring`, `développement`, `business development`, `stratégie`, `nomination`, `prend la direction`, `rejoint`, `nommé`

### Format de sortie attendu d'un signal capté
```json
{
  "company": "Danone",
  "sector": "food",
  "geography": "france",
  "contact_function": "supply_chain",
  "trigger": "Nomination nouveau VP Supply Chain",
  "source": "Les Echos",
  "date": "2026-06-30",
  "url": "https://..."
}
```

---

## Matrice de Ciblage 3D (Étape 2) — ✅ IMPLÉMENTÉE

**Fichier :** `targeting_matrix.json` (racine du projet)

### Structure du fichier
Format JSON avec structure `canonical + synonymes FR/EN` pour chaque entrée :
```json
{
  "canonical": "food",
  "synonyms": ["agroalimentaire", "fmcg", "alimentation", "food & beverage", ...]
}
```

### Logique de scoring
- **Règle :** `score global = min(score_sectoriel, score_géo, score_fonctionnel)` (worst-case)
- Un signal doit être **P1 sur les 3 axes** pour déclencher un outreach

### Périmètre PoC (P1 sur les 3 axes)
| Dimension | P1 |
|---|---|
| Sectoriel | food / agroalimentaire / FMCG |
| Géographique | France, NORAM (USA/Canada), North East Asia (dont HK) |
| Fonctionnel | Marketing, R&D, IT, RH, Finance, Stratégie, Ops, Supply Chain, S&OP, Sales |

Les synonymes incluent les **titres de postes** (CMO, CFO, DSI, CHRO...) pour matcher directement sur les nominations.

---

## Architecture Technique

### Modèle retenu : Hybride
- **Step 1 (scraping)** → Claude Code — scripts Python, tâches planifiées, prod JSON de signaux
- **Steps 2→3→4** → Cowork skills — scoring matrice, identification contact, drafting
- **Point de jonction** : fichier JSON partagé (signals output du scraper)
- Cowork peut appeler les scripts Claude Code via MCP

### Stack envisagée pour le scraping
- Python (requests, feedparser pour RSS, beautifulsoup4 si scraping HTML)
- Sortie : fichier JSON ou JSONL de signaux (`signals_output.jsonl`)
- Planification : cron ou tâche schedulée

---

## Dépendances Inter-Équipes
- **Base credentials Emerton** (autre équipe hackathon) → alimente le drafting (step 4)
- **CVs / Skills mapping** (autre équipe hackathon) → alimente le drafting (step 4)

## Contraintes
- LinkedIn : Chrome connector OK pour identification ciblée (step 3), **pas** pour veille large (trop de tokens)
- Matrice : **ne pas agentifier** dans un premier temps — config JSON manuel suffisante
- HubSpot : connecteur MCP disponible, Ugo a l'accès admin

## Branche Manquante
Triggers M&A / fonds d'investissement / due diligences → à construire avec François (Emerton Strategy)

---

## Fichiers Clés
- `targeting_matrix.json` — matrice de ciblage 3D (config manuelle, PoC food/France/NORAM/NEA)
- `260623 - framing/` — compte-rendu et transcript réunion de cadrage du 23/06
- Miro board : https://miro.com/app/board/uXjVHC_aEe8=/
