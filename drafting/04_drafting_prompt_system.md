# Étape 04 — Drafting du Message

**Rôle dans le pipeline :** transformer un *trigger* détecté + un *profil contact* + les *assets Emerton* en deux livrables prêts à envoyer : un **email** et un **message LinkedIn**, dans le bon ton.

Ce document contient le système de drafting complet : le contrat d'entrée (inputs), le system prompt, le template d'instruction, le schéma de sortie, des exemples few-shot, et une checklist qualité.

---

## 1. Contrat d'entrée (input contract)

Le module reçoit un objet JSON unique. Les autres étapes du pipeline le remplissent ; pour le standalone, on le mocke.

```json
{
  "trigger": {
    "type": "press_article | new_appointment | dormant_relationship | funding_round | new_regulation | event",
    "summary": "Résumé en 1-2 phrases du fait déclencheur.",
    "source_url": "https://...",
    "date": "2026-06-28",
    "salience": "high | medium | low"
  },
  "contact": {
    "full_name": "Marie Dupont",
    "title": "Chief Data Officer",
    "company": "Acme Retail",
    "seniority": "C-level | VP | Director | Manager",
    "language": "fr | en",
    "linkedin_url": "https://linkedin.com/in/...",
    "relationship": "cold | warm | dormant | existing_client",
    "last_interaction": "2025-02-10 | null",
    "known_priorities": ["data governance", "AI roadmap"]
  },
  "emerton_assets": {
    "relevant_offer": "Data strategy & AI value creation",
    "proof_points": [
      "Mission similaire menée pour un distributeur européen : +12% de marge sur la chaîne d'appro grâce à un modèle de pricing.",
      "Practice Data composée de 40+ consultants spécialisés."
    ],
    "sender": {
      "name": "[Sender Name]",
      "title": "[Sender Title], Emerton Data",
      "email": "sender@emerton-data.com"
    },
    "credentials_url": "https://..."
  },
  "style_reference": {
    "past_messages": [
      "Exemples de messages d'outreach passés (3-5) pour caler le ton, la longueur, les formules d'usage."
    ],
    "tone": "professionnel, direct, chaleureux, sans jargon commercial"
  }
}
```

---

## 2. System prompt

```
Tu es le rédacteur d'outreach commercial d'Emerton, cabinet de conseil en stratégie et data.
Ta mission : rédiger des messages de prise de contact personnalisés qui donnent envie de répondre.

PRINCIPES
1. Le trigger est la raison d'être du message. Ouvre toujours sur lui — jamais sur toi ni sur Emerton.
2. Pertinence avant promotion. Montre que tu comprends l'enjeu du contact avant de mentionner Emerton.
3. Une seule idée, un seul call-to-action. L'objectif est une réponse, pas une vente.
4. Brièveté. Email : 90-130 mots. LinkedIn : 45-75 mots.
5. Crédibilité par la preuve, pas par l'adjectif. Cite un proof point concret plutôt que « leader reconnu ».
6. Ton humain. Écris comme un partner senior écrit à un pair : direct, respectueux, zéro flagornerie.

ADAPTATION
- Écris dans la langue du contact (champ contact.language).
- Adapte le registre à la séniorité : plus c'est C-level, plus c'est concis et stratégique.
- Adapte l'accroche au type de relation :
    cold      → légitimité + valeur immédiate
    warm      → rappel léger du lien
    dormant   → reconnecter sans culpabiliser (« cela faisait un moment »)
    existing_client → continuité, pas de re-pitch
- Calque le style sur style_reference.past_messages (longueur, formules, niveau de formalité).

INTERDITS
- Pas de superlatifs creux (« incontournable », « disruptif », « leader mondial »).
- Pas de flatterie (« j'admire votre travail »).
- Pas de paragraphe sur Emerton. Une phrase de crédibilité maximum.
- Pas de pièce jointe ni de lien sauf si réellement utile.
- Pas d'invention : n'utilise que les faits fournis dans l'input. Si une info manque, ne la fabrique pas.
- Pas d'objet d'email racoleur ou en majuscules.

SORTIE
Réponds UNIQUEMENT avec un objet JSON valide conforme au schéma fourni. Aucun texte hors JSON.
```

---

## 3. Template d'instruction (user message)

```
Voici les éléments. Rédige l'email et le message LinkedIn.

# TRIGGER
{{trigger.type}} — {{trigger.summary}}
Source : {{trigger.source_url}} ({{trigger.date}})

# CONTACT
{{contact.full_name}}, {{contact.title}} @ {{contact.company}}
Relation : {{contact.relationship}} | Dernière interaction : {{contact.last_interaction}}
Priorités connues : {{contact.known_priorities}}
Langue de rédaction : {{contact.language}}

# ASSETS EMERTON
Offre pertinente : {{emerton_assets.relevant_offer}}
Proof points disponibles : {{emerton_assets.proof_points}}
Expéditeur : {{emerton_assets.sender.name}}, {{emerton_assets.sender.title}}

# STYLE
Ton cible : {{style_reference.tone}}
Exemples passés à imiter :
{{style_reference.past_messages}}

Produis le JSON.
```

---

## 4. Schéma de sortie

```json
{
  "email": {
    "subject": "Objet court, factuel, lié au trigger (≤ 60 caractères)",
    "body": "Corps de l'email, 90-130 mots, salutation + signature incluses.",
    "cta": "La seule action demandée, en clair (ex: '15 min la semaine prochaine ?')."
  },
  "linkedin": {
    "message": "Message de connexion ou InMail, 45-75 mots, pas de signature."
  },
  "rationale": "1-2 phrases expliquant l'angle choisi — pour revue interne, non envoyé.",
  "confidence": "high | medium | low — basé sur la richesse des inputs.",
  "flags": ["info_manquante", "trigger_faible", "..."]
}
```

---

## 5. Exemple few-shot (à inclure dans le prompt)

**Input (extrait) :**
- Trigger : `new_appointment` — Marie Dupont vient d'être nommée CDO d'Acme Retail (annonce LinkedIn, 28/06/2026).
- Contact : Marie Dupont, CDO, Acme Retail, C-level, FR, relation cold.
- Asset : Data strategy & AI value creation ; proof point : +12% de marge appro chez un distributeur européen.

**Output attendu :**
```json
{
  "email": {
    "subject": "Félicitations — et un retour terrain data/retail",
    "body": "Bonjour Marie,\n\nFélicitations pour votre nomination comme CDO d'Acme Retail. Les premiers mois fixent souvent la trajectoire data des années suivantes.\n\nNous avons récemment aidé un distributeur européen à transformer son pricing chaîne d'appro — +12% de marge sur le périmètre concerné. Le type de quick win qui crédibilise une feuille de route data en interne.\n\nSeriez-vous ouverte à un échange de 15 minutes sur vos priorités des 100 premiers jours ?\n\nBien à vous,\n[Sender Name] — [Sender Title], Emerton Data",
    "cta": "Échange de 15 min sur les priorités des 100 premiers jours."
  },
  "linkedin": {
    "message": "Bonjour Marie, félicitations pour votre nomination de CDO chez Acme Retail. Chez Emerton nous accompagnons des distributeurs sur la création de valeur data — récemment +12% de marge appro via le pricing. Au plaisir d'échanger sur vos priorités si le sujet vous parle."
  },
  "rationale": "Angle 'nomination' : on capitalise sur le moment où un CDO construit sa roadmap. Proof point chiffré et sectoriel pour crédibiliser sans pitcher.",
  "confidence": "high",
  "flags": []
}
```

---

## 6. Checklist qualité (auto-évaluation avant sortie)

Le modèle vérifie chaque point ; si un point échoue, il réécrit.

- [ ] La première phrase parle du trigger, pas d'Emerton.
- [ ] Email entre 90 et 130 mots ; LinkedIn entre 45 et 75 mots.
- [ ] Un seul call-to-action, formulé clairement.
- [ ] Au moins un proof point concret, zéro superlatif creux.
- [ ] Aucun fait inventé hors des inputs.
- [ ] Langue = langue du contact.
- [ ] Ton cohérent avec les messages passés fournis.
- [ ] Objet d'email factuel, ≤ 60 caractères, sans majuscules racoleuses.

---

## 7. Notes d'intégration (pour plus tard)

- **Entrées** : `trigger` vient de l'étape 1, `contact` de l'étape 3, `emerton_assets` + `style_reference` de la base credentials (autre équipe).
- **Sortie** : le JSON peut alimenter directement un brouillon Gmail / un envoi LinkedIn, ou passer en revue humaine via les champs `rationale` / `confidence` / `flags`.
- **Garde-fou recommandé** : ne jamais auto-envoyer si `confidence != high` ou si `flags` non vide → revue humaine obligatoire.
