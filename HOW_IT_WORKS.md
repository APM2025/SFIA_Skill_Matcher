# How the SFIA Skill Matcher Works - Explained for Everyone

## Introduction

You might be wondering: "How does the app actually figure out which skills match my experience?" This guide explains the technology behind the SFIA Skill Matcher in plain English, so you can understand and trust how it works.

**No technical background needed!** We'll explain everything using everyday analogies.

---

## The Big Picture

Imagine you're at a library looking for books similar to one you loved. A good librarian doesn't just look at the title - they understand what the book is *about* and can recommend similar books even if they have completely different titles.

The SFIA Skill Matcher works the same way:
1. It understands what your work experience is *about* (not just matching keywords)
2. It compares this understanding to all SFIA skills
3. It finds and ranks the best matches
4. It explains why each skill matched

Let's break down each part of this process.

---

## Part 1: The Knowledge Graph (SFIA's Digital Library)

### What is it?

Think of a knowledge graph like a **super-organized filing system** where everything is connected.

In a normal database, information is stored in simple tables like a spreadsheet:
```
Skill Name          | Code | Description
--------------------|------|------------------
Programming         | PROG | Develops software...
Testing             | TEST | Tests software quality...
```

A **knowledge graph** is much richer. It stores not just facts, but also *relationships*:
```
Programming (PROG)
  ├─ is part of → "Development and Implementation" category
  ├─ requires → "Logic and problem-solving"
  ├─ relates to → Testing (TEST)
  ├─ has 7 levels → Level 1, Level 2, ... Level 7
  └─ each level has → specific responsibilities
```

### What is RDF?

**RDF stands for "Resource Description Framework"** - a fancy name for a standard way to describe knowledge graphs.

Think of it like a universal grammar for organizing information. Just like English grammar has rules (subject-verb-object: "The cat ate fish"), RDF has rules for describing facts:

**Normal way:**
- "Programming is a skill"
- "Programming has code PROG"
- "Programming involves developing software"

**RDF way (structured connections):**
- Programming → is-a → Skill
- Programming → has-code → "PROG"
- Programming → involves → developing software
- Programming → belongs-to → Development-and-Implementation

The SFIA Foundation publishes their framework as an RDF file (`.ttl` format). This file contains:
- All 121 SFIA skills
- Descriptions of what each skill involves
- The 7 levels of responsibility
- Categories and relationships between skills

### Why use a knowledge graph?

**Benefits:**
1. **Rich context**: The app doesn't just see "Programming" - it sees that Programming relates to Testing, belongs to Development, and has specific responsibilities at each level
2. **Relationships matter**: If your evidence mentions "debugging" and "code quality," the graph knows these relate to both Programming AND Testing
3. **Standardized data**: The SFIA Foundation maintains this official structure, so the app always uses authoritative, up-to-date skill definitions

**Analogy:** 
- Regular database = dictionary (just definitions)
- Knowledge graph = encyclopedia with cross-references (definitions + how everything connects)

---

## Part 2: Understanding Meaning with AI Embeddings

### The Challenge

When you write "I automated database backups using Python scripts," how does the computer know this relates to:
- Programming/software development (PROG)
- IT Infrastructure (ITOP)
- Automation (AUTO)

It can't just look for exact word matches because:
- Your evidence might say "scripts" while SFIA says "programs"
- You might say "automated" while SFIA says "systematic execution"
- The meanings are similar, but the words are different

### What are Embeddings?

**Embeddings** are a way to convert text into numbers that capture *meaning*, not just words.

**Analogy: The Flavor Profile**

Imagine describing foods by their flavor profile:
- Sweetness: 0-10
- Saltiness: 0-10
- Spiciness: 0-10
- Bitterness: 0-10

Now you can say:
- Chocolate = [8 sweet, 1 salty, 0 spicy, 3 bitter]
- Caramel = [9 sweet, 2 salty, 0 spicy, 0 bitter]
- Coffee = [1 sweet, 0 salty, 0 spicy, 7 bitter]

Chocolate and caramel are *similar* (both high sweetness, low bitterness) even though they're different foods. Coffee is *different* (high bitterness, low sweetness).

**Text embeddings work the same way**, but instead of 4 dimensions (sweet/salty/spicy/bitter), they use 384 dimensions to capture meaning!

Example:
```
"I wrote Python code" → [0.2, 0.8, 0.1, 0.5, ...]  (384 numbers)
"I developed software" → [0.3, 0.7, 0.2, 0.4, ...]  (384 numbers)
"I baked a cake" → [0.9, 0.1, 0.3, 0.8, ...]  (384 numbers)
```

The first two are *close together* in meaning (similar numbers), while the third is *far away* (different numbers).

### How the App Uses Embeddings

**Step 1: Convert your evidence to numbers**
When you submit your STAR evidence, the app converts it into an embedding (384 numbers that capture its meaning).

**Step 2: Convert all SFIA skills to numbers**
The app does the same for every SFIA skill description.
- "Programming/software development: Develops software components..." → [0.3, 0.7, 0.2, ...]
- "Testing: Tests and evaluates software quality..." → [0.4, 0.6, 0.3, ...]

**Step 3: Calculate similarity**
Now the app can mathematically compare your evidence to each skill:

```
Your evidence: [0.2, 0.8, 0.1, 0.5, ...]
Programming:    [0.3, 0.7, 0.2, 0.4, ...]  → Similarity: 92%
Testing:        [0.4, 0.6, 0.3, 0.6, ...]  → Similarity: 78%
Baking:         [0.9, 0.1, 0.3, 0.8, ...]  → Similarity: 15%
```

This is called **semantic similarity** - understanding meaning, not just matching words.

### The AI Model

The app uses a pre-trained AI model called **"all-MiniLM-L6-v2"**. This is like a language expert that has:
- Read millions of English sentences
- Learned what words mean and how they relate
- Been trained to convert text into meaningful embeddings

**Key point:** The model doesn't need to be trained on SFIA specifically! Because it understands English meaning, it can compare ANY text to SFIA skills.

**Trust factor:** This is the same technology used by:
- Google Search (to understand what you're looking for)
- Gmail (to categorize emails)
- Chatbots (to understand questions)

It's well-tested and widely used in professional applications.

---

## Part 3: The STAR Weighting System

Not all parts of your evidence are equally important. The app assigns different weights to each STAR component.

### Why STAR?

The **STAR format** (Situation, Task, Action, Result) is an interview framework designed to structure evidence. Each part serves a purpose:

- **Situation**: Context (where/when/why)
- **Task**: Objective (what needed to be done)
- **Action**: What YOU did (the most important!)
- **Result**: Outcome (proof it worked)

For skill matching, **what you DID (Action)** matters most. The situation and task provide context, and the result provides validation.

### How the App Weights STAR

The app creates **two separate embeddings** from your evidence:

**1. Action Embedding (60% weight)**
- Focus: The "Action" section
- Why it matters most: This describes the actual WORK you did
- Example: *"I analyzed the database schema, identified redundancies, wrote migration scripts, and documented the changes"*

**2. Context Embedding (40% weight)**
- Focus: Situation + Task + Result combined
- Why it matters: Provides additional clues about the skill domain
- Example: *"Database performance issues... needed to improve efficiency... resulted in 60% faster queries"*

**The Formula:**
```
Final Score = (60% × Action Similarity) + (40% × Context Similarity)
```

### Why This Approach?

Think of applying for a job:
- Your **actions** are your qualifications (what you can do)
- The **context** is supporting evidence (proof you've done it)

If someone says:
- *"I worked on databases"* (vague action) but *"I fixed a critical issue that saved the company $50k"* (strong result)
  
vs.
  
- *"I redesigned the entire database architecture, normalized to 3NF, implemented indexing strategies, and trained the team"* (detailed action) but *"in a university project"* (modest context)

The second person demonstrated MORE skill, even if the context was smaller. The action detail matters most!

### Dual Retrieval Strategy

The app searches TWICE to capture different signals:

**Search 1: Action-based (60 candidates)**
- Question: "Which skills involve THIS TYPE OF WORK?"
- Based on: Your Action section
- Catches: Direct skill matches

**Search 2: Context-based (40 candidates)**
- Question: "Which skills appear in THIS TYPE OF SITUATION?"
- Based on: Situation + Task + Result
- Catches: Domain-related skills you might have missed

**Then:** Combine both lists, remove duplicates, and rank by final score.

**Analogy:** 
Imagine looking for a restaurant:
- Search 1: "Best Italian food" (direct match)
- Search 2: "Romantic dinner spots" (contextual match)
- Combined: You find Italian restaurants that are also romantic

---

## Part 4: Additional Scoring Factors

Beyond semantic similarity, the app applies two more adjustments:

### 1. Keyword Boosting (+5%)

**What it is:** If your evidence contains specific technical terms often associated with a skill, that skill gets a small bonus.

**Example:**
You mention: "Python," "debugging," "unit tests"
These words frequently appear in job postings for:
- Programming/software development (PROG)
- Testing (TEST)

**How it works:**
The app has a mapping file (`job_roles_mapping.json`) that lists common job titles and keywords for each SFIA skill:
```json
{
  "PROG": {
    "job_roles": ["Software Developer", "Python Engineer", "Programmer"],
    "keywords": ["python", "debugging", "code", "script"]
  }
}
```

If your evidence mentions ANY of these keywords, Programming (PROG) gets +5% added to its score.

**Why only +5%?** 
Keyword matching is helpful but not as reliable as semantic understanding. It's a tiebreaker, not a primary signal.

**Analogy:** 
It's like a chef recognizing ingredients. If you mention "oregano" and "mozzarella," they'll guess you're talking about Italian food - but the full recipe (semantic meaning) is more important than individual ingredients (keywords).

### 2. Level Modifier (±15%)

**What it is:** If you describe your level of responsibility, the app adjusts scores based on whether each skill matches your level.

**How level detection works:**

The app compares your responsibility description to SFIA's 7 standard levels:

| Level | Name | Key Phrases |
|-------|------|-------------|
| 1 | Follow | "under direct supervision," "learning," "following instructions" |
| 2 | Assist | "under general supervision," "some independence," "routine tasks" |
| 3 | Apply | "work independently," "guide others," "solve problems" |
| 4 | Enable | "lead small teams," "coordinate," "influence specialists" |
| 5 | Ensure | "lead significant teams," "accountable for outcomes," "strategic input" |
| 6 | Initiate | "lead organization-wide initiatives," "define strategy" |
| 7 | Set Strategy | "enterprise-level leadership," "industry influence" |

**Example:**
You write: *"I worked independently on this project, making technical decisions and mentoring a junior developer"*

The app:
1. Converts this to an embedding
2. Compares it to all 7 level descriptions
3. Finds the closest match (likely Level 3 or 4)
4. Detects your level: **Level 3 (Apply)**

**Then, for each skill match:**
- If the skill is commonly performed at Level 3: **+15% bonus**
- If the skill is 1 level away (Level 2 or 4): **+5% bonus**
- If the skill is 2+ levels away (Level 1 or 5+): **-15% penalty**

**Why this matters:**

Some skills have different expectations at different levels:

- "Programming" at Level 2 = Write simple scripts under supervision
- "Programming" at Level 4 = Design complex systems and lead development

If you described Level 2 responsibilities but the app matched you to Level 4 Programming, the score is adjusted down because there's a mismatch.

**Trust factor:** This prevents over-claiming. The app won't say you demonstrated "Strategic Leadership (Level 6)" if you described working under supervision.

---

## Part 5: The Complete Matching Process

Now let's see how everything works together, step by step.

### Your Evidence Input

```
Situation: The customer database was slow and error-prone
Task: Improve database performance and reduce errors
Action: I analyzed the schema, identified redundant tables, redesigned 
        it using normalization principles, wrote SQL migration scripts,
        and trained the team on the new structure
Result: Query time improved 60%, errors dropped 40%
Level: I worked independently and made technical decisions
```

### Step 1: Parse and Prepare

The app separates your STAR sections:
- **Action text**: "I analyzed the schema, identified..."
- **Context text**: "database was slow... improve performance... 60% improvement..."
- **Level text**: "worked independently and made technical decisions"

### Step 2: Create Embeddings

Converts text to numerical representations:
```
Action embedding:    [0.23, 0.81, 0.15, 0.52, ...] (384 numbers)
Context embedding:   [0.19, 0.76, 0.22, 0.48, ...] (384 numbers)
Level embedding:     [0.41, 0.63, 0.28, 0.55, ...] (384 numbers)
```

### Step 3: Retrieve Candidates

**Action-based search (top 60):**
Compares your action embedding to all 121 SFIA skill embeddings:
- Database design (DBDS): 0.89 similarity
- Programming (PROG): 0.82 similarity
- Data management (DTAN): 0.78 similarity
- (etc... 60 total skills)

**Context-based search (top 40):**
Compares your context embedding to all skills:
- Database design (DBDS): 0.85 similarity
- Business analysis (BUAN): 0.71 similarity
- Performance testing (TEST): 0.68 similarity
- (etc... 40 total skills)

**Combine and deduplicate:**
Total unique candidates: ~75 skills

### Step 4: Detect Level

Compares your level description to the 7 SFIA levels:
```
Level 1 (Follow):         45% match
Level 2 (Assist):         62% match
Level 3 (Apply):          88% match ← Best match!
Level 4 (Enable):         71% match
Level 5 (Ensure):         38% match
Level 6 (Initiate):       22% match
Level 7 (Set Strategy):   12% match
```

**Detected level: 3 (Apply)** - "Works independently, guides others"

### Step 5: Calculate Final Scores

For each candidate skill, calculate:

**Example: Database Design (DBDS)**

```
Action similarity:     0.89
Context similarity:    0.85
Weighted score:        (0.60 × 0.89) + (0.40 × 0.85) = 0.874

Keywords found:        "database", "schema", "SQL", "normalization"
Keyword boost:         +0.05

Skill typical level:   Level 3 (matches your detected level!)
Level modifier:        +0.15

FINAL SCORE:          0.874 + 0.05 + 0.15 = 1.074 (capped at 1.0) = 1.00
Displayed as:         100%
```

**Example: Programming (PROG)**

```
Action similarity:     0.82
Context similarity:    0.73
Weighted score:        (0.60 × 0.82) + (0.40 × 0.73) = 0.784

Keywords found:        "scripts"
Keyword boost:         +0.05

Skill typical level:   Level 2-4 (close to your level)
Level modifier:        +0.05

FINAL SCORE:          0.784 + 0.05 + 0.05 = 0.884
Displayed as:         88%
```

**Example: Strategic Planning (STPL)**

```
Action similarity:     0.41
Context similarity:    0.38
Weighted score:        (0.60 × 0.41) + (0.40 × 0.38) = 0.398

Keywords found:        none
Keyword boost:         0

Skill typical level:   Level 6-7 (much higher than your level)
Level modifier:        -0.15

FINAL SCORE:          0.398 + 0 - 0.15 = 0.248
Displayed as:         25%
```

### Step 6: Rank and Filter

- Sort all skills by final score (highest first)
- Keep only the **top 5 unique skills**
- Remove duplicates (same skill at different levels)

**Your Results:**
1. Database Design (DBDS) - 100%
2. Programming/software development (PROG) - 88%
3. Data Management (DTAN) - 81%
4. Testing (TEST) - 76%
5. Technical Writing (INCA) - 68%

### Step 7: Extract Evidence Snippets

For each match, the app identifies which part of your evidence was most relevant:

**Database Design:** *"I analyzed the schema, identified redundant tables, redesigned it using normalization principles"*

This helps you see WHY the match was made.

### Step 8: Generate Justifications

The app creates human-readable explanations by:
- Identifying which keywords contributed
- Noting level alignment
- Explaining the semantic match

**Example justification for Database Design:**
*"Strong match based on: database schema analysis, normalization techniques, SQL scripting. Your responsibility level (independent work with technical decisions) matches typical Level 3 performance for this skill."*

---

## Part 6: The Refine Feature

### What if a match is wrong?

Sometimes the initial match isn't quite right. Maybe:
- You meant "testing code quality" not "testing hardware"
- The work was more about "analysis" than "development"
- The context was educational, not professional

### How Refine Works

When you click "Refine this match" and add a clarification like:

*"This was more about data analysis than database administration"*

The app:

1. **Blends your clarification with the original evidence**
   - Original action: 80% weight
   - Clarification: 20% weight
   - Creates a new, adjusted embedding

2. **Re-runs the entire matching process**
   - Using the adjusted embedding
   - Applies all the same scoring rules

3. **Returns updated matches**
   - Data Analysis (DTAN) now scores higher
   - Database Administration (DBAD) scores lower

**Analogy:**
It's like telling a librarian: "I liked that mystery book, but I want more psychological thriller and less detective procedural." They'll recommend different books based on your clarification.

---

## Part 7: Caching for Speed

### The First-Run Problem

Converting text to embeddings requires significant computation. The SFIA framework has 121 skills, and computing embeddings for all of them takes ~30 seconds the first time.

### How Caching Works

**After the first run:**
1. The app saves all SFIA skill embeddings to disk (in `.embedding_cache/`)
2. Next time you start the app, it loads these saved embeddings in ~1 second
3. Only YOUR evidence needs to be converted (takes ~100 milliseconds)

**Analogy:**
The first time you cook a new recipe, you have to measure all ingredients, look up techniques, etc. (30 minutes). The second time, you've written it down and just follow your notes (5 minutes).

**Trust factor:** The cached embeddings are based on a mathematical hash of the SFIA data. If the SFIA file changes, the cache automatically invalidates and recomputes.

---

## Part 8: Why This Approach is Trustworthy

### 1. Uses Official SFIA Data

The app reads directly from the official SFIA 9 RDF file published by the SFIA Foundation. It doesn't make up skill definitions - it uses the authoritative source.

### 2. Transparent Scoring

Every match shows you:
- ✅ The similarity score (how close the match is)
- ✅ The relevant evidence (which part of your text matched)
- ✅ The justification (why the match was made)
- ✅ The level alignment (whether your level matches the skill)

You can see exactly WHY each skill was matched.

### 3. Proven AI Technology

The sentence-transformer model used is:
- Open source (anyone can inspect the code)
- Widely used in industry
- Based on published research
- Trained on millions of text examples

It's not experimental - it's production-grade technology used by major companies.

### 4. Multi-Signal Validation

The app doesn't rely on just one method:
- ✅ Semantic similarity (meaning-based)
- ✅ Keyword matching (term-based)
- ✅ Level alignment (responsibility-based)
- ✅ Context analysis (domain-based)

Multiple independent signals reduce the chance of false matches.

### 5. Conservative Scoring

The app is designed to UNDER-claim rather than OVER-claim:
- Level mismatches are penalized
- Generic evidence gets lower scores
- Multiple filters prevent false positives

You won't see inflated results - if the match is weak, the score will be low.

### 6. No Hidden Training

The AI model is pre-trained on general English text, NOT specifically on SFIA. This means:
- It can't be biased toward certain skills
- It applies consistent logic to all skills
- It generalizes from language understanding, not memorization

---

## Common Questions

### Q: Does the app "learn" from my submissions?

**A:** No. The app doesn't train or update the AI model based on your evidence. Each matching is independent. This ensures:
- Consistency: Everyone gets the same matching logic
- Privacy: Your data doesn't influence other users' results
- Predictability: The app behaves the same way every time

### Q: Can two people with the same evidence get different results?

**A:** No, the matching is deterministic. Same evidence → same results. The only variation would come from:
- Different SFIA data files (e.g., SFIA 9 vs. SFIA 10)
- Different level descriptions
- App updates (which would be documented)

### Q: How accurate is the level detection?

**A:** Level detection is based on semantic matching to SFIA's official level descriptions. It's quite reliable when you provide clear responsibility descriptions (e.g., "I worked under supervision" vs. "I led a team of 10"). 

However, it's a **suggestion**, not a certification. Use it as a starting point and adjust based on your actual role.

### Q: What if I describe multiple skills in one STAR example?

**A:** That's perfectly fine! The semantic matching will identify multiple relevant skills. For example, if you describe:

*"I designed a database, wrote Python scripts to populate it, and tested the data quality"*

You'll likely match:
- Database Design (DBDS)
- Programming (PROG)
- Testing (TEST)

This is actually good - it shows you demonstrated multiple skills in one project.

### Q: Why did an unexpected skill appear in my matches?

**A:** This can happen for a few reasons:

1. **Semantic overlap**: Some skills have overlapping descriptions. "Data Analysis" and "Business Intelligence" are related.

2. **Context clues**: Your Situation/Task/Result might have mentioned a domain that relates to an unexpected skill.

3. **Generic evidence**: If your evidence is vague, multiple skills might match with moderate scores.

**What to do:** Look at the justification and evidence snippet. If it doesn't make sense, use the Refine feature to clarify.

### Q: Can the app make mistakes?

**A:** Yes, like any AI system, it's not perfect. Common issues:

- **Ambiguous evidence**: Vague descriptions can match multiple skills equally
- **Rare terminology**: Very specialized jargon might not match well
- **Context misinterpretation**: The app might emphasize context over action if your Action section is brief

**Mitigation:** The app shows you match scores, evidence snippets, and justifications so you can judge whether the matches make sense. Always use your own judgment!

### Q: Is my data sent to OpenAI, Google, or other third parties?

**A:** No! The app runs the AI model locally (or on the server where it's hosted). Your evidence text:
- ✅ Stays within the application
- ✅ Is not sent to external APIs
- ✅ Is not stored in a database
- ✅ Is discarded when your session ends

The only external resource is downloading the AI model once (from HuggingFace), but your actual evidence never leaves the app.

---

## Summary: The Complete Journey

Let's recap the full matching process:

```
1. YOUR EVIDENCE
   ↓
   [Parse STAR sections]
   ↓
2. ACTION EMBEDDING (60% weight) ← Converts action text to 384 numbers
   ↓
3. CONTEXT EMBEDDING (40% weight) ← Converts situation+task+result to 384 numbers
   ↓
4. SEMANTIC SEARCH ← Compares embeddings to all 121 SFIA skills
   ↓
5. RETRIEVE CANDIDATES ← Get top 60 (action) + top 40 (context)
   ↓
6. LEVEL DETECTION ← Compare responsibility to 7 SFIA levels
   ↓
7. CALCULATE SCORES ← Weighted similarity + keyword boost + level modifier
   ↓
8. RANK & FILTER ← Sort by score, keep top 5
   ↓
9. EXTRACT SNIPPETS ← Find relevant evidence for each match
   ↓
10. YOUR RESULTS
    • Top 5 matching skills
    • Scores (as percentages)
    • Evidence snippets
    • Justifications
    • Detected level
```

**Key Technologies:**
- 📚 **Knowledge Graph (RDF)**: Structured SFIA data with relationships
- 🧠 **AI Embeddings**: Convert text to meaning-capturing numbers
- 📊 **Semantic Similarity**: Compare meanings, not just words
- ⚖️ **STAR Weighting**: Action (60%) + Context (40%)
- 🎯 **Multi-Signal Scoring**: Semantic + Keywords + Level alignment
- 🔍 **Dual Retrieval**: Action-based + Context-based search

---

## Conclusion

The SFIA Skill Matcher uses sophisticated AI technology, but its logic is straightforward:

1. **Understand** what your evidence means (not just what words it contains)
2. **Compare** that meaning to official SFIA skill descriptions
3. **Adjust** scores based on keywords and responsibility level
4. **Rank** skills by match quality
5. **Explain** why each match was made

Everything is transparent, traceable, and based on authoritative SFIA data.

**You can trust the results because:**
- ✅ The technology is proven and widely used
- ✅ The process is transparent (you see scores, snippets, and justifications)
- ✅ Multiple signals validate each match
- ✅ It uses official SFIA definitions
- ✅ It's conservative (won't over-claim skills)

Use the app as a tool to help you identify and articulate your skills - but always apply your own judgment to the results!

---

**Questions or want to learn more?** Check out the [USER_GUIDE.md](USER_GUIDE.md) for practical usage tips or [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for technical deep-dives.
