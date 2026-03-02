import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class Chapter:
    id: str
    title: str
    description: str


@dataclass
class KnowledgeArea:
    id: str
    title: str
    category: str
    description: str
    topics: List[str]
    chapters: List[Chapter] = field(default_factory=list)


@dataclass
class BodyOfKnowledge:
    bok_id: str
    name: str
    version: str
    description: str
    knowledge_areas: Dict[str, KnowledgeArea]


class BokParser:
    def __init__(self, bok_dir: str):
        self.bok_dir = Path(bok_dir)
        self.boks: Dict[str, BodyOfKnowledge] = {}
        self._load_all_boks()

    def _load_all_boks(self):
        if not self.bok_dir.exists():
            return
        for json_file in self.bok_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    bok = self._parse_bok(data)
                    if bok:
                        self.boks[bok.bok_id] = bok
            except Exception as e:
                print(f"Error loading {json_file}: {e}")

    def _parse_bok(self, data: dict) -> Optional[BodyOfKnowledge]:
        try:
            kas = {}
            for ka_data in data.get('knowledge_areas', []):
                chapters = [
                    Chapter(
                        id=ch.get('id', ''),
                        title=ch.get('title', ''),
                        description=ch.get('description', '')
                    )
                    for ch in ka_data.get('chapters', [])
                ]
                ka = KnowledgeArea(
                    id=ka_data.get('id', ''),
                    title=ka_data.get('title', ''),
                    category=ka_data.get('category', ''),
                    description=ka_data.get('description', ''),
                    topics=ka_data.get('topics', []),
                    chapters=chapters
                )
                kas[ka.id] = ka

            return BodyOfKnowledge(
                bok_id=data.get('bok_id', ''),
                name=data.get('name', ''),
                version=data.get('version', ''),
                description=data.get('description', ''),
                knowledge_areas=kas
            )
        except Exception as e:
            print(f"Error parsing BoK data: {e}")
            return None

    def get_bok_summaries(self) -> Dict[str, dict]:
        return {
            bok_id: {
                "name": bok.name,
                "version": bok.version,
                "description": bok.description
            }
            for bok_id, bok in self.boks.items()
        }

    def get_knowledge_areas(self, bok_id: str) -> Optional[Dict[str, dict]]:
        if bok_id not in self.boks:
            return None
        return {
            ka.id: {
                "title": ka.title,
                "category": ka.category,
                "description": ka.description,
                "topics": ka.topics,
                "chapter_count": len(ka.chapters)
            }
            for ka in self.boks[bok_id].knowledge_areas.values()
        }

    def get_ka_context(self, bok_id: str, ka_id: str) -> Optional[dict]:
        bok = self.boks.get(bok_id)
        if not bok:
            return None
        ka = bok.knowledge_areas.get(ka_id)
        if not ka:
            return None
        return {
            "bok_name": bok.name,
            "ka_id": ka.id,
            "ka_title": ka.title,
            "ka_category": ka.category,
            "ka_description": ka.description,
            "ka_topics": ka.topics,
            "ka_chapters": [
                {"id": ch.id, "title": ch.title, "description": ch.description}
                for ch in ka.chapters
            ]
        }
