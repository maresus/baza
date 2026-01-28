"""
Semantic Knowledge Graph - Povezan graf medicinskih konceptov

FUNKCIONALNOST:
1. Medical concept graph - Simptomi → Specialisti, Posegi → Priprave
2. Contextual answers - povezane informacije
3. Related info suggestions - priporočila glede na kontekst
4. Urgency indicators - oznake nujnosti

UPORABA:
    from app.services.knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph()
    result = kg.query_symptoms(["bolečina v kolenu", "otekanje"])
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Tipi vozlišč v grafu"""
    SYMPTOM = "symptom"
    SPECIALIST = "specialist"
    SERVICE = "service"
    PREPARATION = "preparation"
    CONDITION = "condition"
    BODY_PART = "body_part"


class UrgencyLevel(Enum):
    """Stopnje nujnosti"""
    ROUTINE = 1      # Rutinski pregled
    SOON = 2         # V nekaj tednih
    PRIORITY = 3     # V nekaj dneh
    URGENT = 4       # V 24h
    EMERGENCY = 5    # Takoj - 112


@dataclass
class GraphNode:
    """Vozlišče v knowledge grafu"""
    id: str
    name: str
    name_sl: str  # Slovensko ime
    node_type: NodeType
    properties: Dict[str, Any] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "name_sl": self.name_sl,
            "type": self.node_type.value,
            "properties": self.properties or {}
        }


@dataclass
class GraphEdge:
    """Povezava v knowledge grafu"""
    source_id: str
    target_id: str
    relation: str
    weight: float = 1.0
    properties: Dict[str, Any] = None


class KnowledgeGraph:
    """Semantični graf medicinskih konceptov."""

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._build_graph()

    def _add_node(self, node: GraphNode) -> None:
        """Doda vozlišče v graf."""
        self.nodes[node.id] = node

    def _add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        weight: float = 1.0,
        properties: Dict = None
    ) -> None:
        """Doda povezavo v graf."""
        self.edges.append(GraphEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            weight=weight,
            properties=properties or {}
        ))

    def _build_graph(self) -> None:
        """Zgradi knowledge graf."""

        # ================================================================
        # SPECIALISTI
        # ================================================================
        specialists = [
            ("dermatolog", "Dermatolog", "Specialist za kožne bolezni"),
            ("ortoped", "Ortoped", "Specialist za kosti in sklepe"),
            ("okulist", "Okulist", "Specialist za oči"),
            ("alergolog", "Alergolog", "Specialist za alergije"),
            ("internist", "Internist", "Specialist za notranje bolezni"),
            ("fizioterapevt", "Fizioterapevt", "Specialist za rehabilitacijo"),
        ]

        for spec_id, name, desc in specialists:
            self._add_node(GraphNode(
                id=spec_id,
                name=name,
                name_sl=name,
                node_type=NodeType.SPECIALIST,
                properties={"description": desc}
            ))

        # ================================================================
        # SIMPTOMI
        # ================================================================
        symptoms = [
            # Kožni simptomi
            ("bolecina_koze", "Bolečina kože", ["boli koža", "peče koža", "srbi"]),
            ("izpuscaj", "Izpuščaj", ["izpuščaji", "rdečica", "mozolji", "akne"]),
            ("sprememba_koznega_znamenja", "Sprememba kožnega znamenja", ["znamenje", "madež", "pega"]),
            ("suha_koza", "Suha koža", ["luščenje", "razpokana koža"]),

            # Ortopedski simptomi
            ("bolecina_kolena", "Bolečina v kolenu", ["boli koleno", "koleno", "kolena"]),
            ("bolecina_hrbta", "Bolečina v hrbtu", ["boli hrbet", "hrbtenica", "križ"]),
            ("bolecina_rame", "Bolečina v rami", ["boli rama", "ramena"]),
            ("otekanje_sklepa", "Otekanje sklepa", ["oteklina", "otečen sklep"]),
            ("omejeno_gibanje", "Omejeno gibanje", ["ne morem premikat", "toga"]),

            # Očesni simptomi
            ("slab_vid", "Slab vid", ["slabo vidim", "zamegljen vid", "meglen vid"]),
            ("rdece_oci", "Rdeče oči", ["rdeče oko", "pekoče oči"]),
            ("suhe_oci", "Suhe oči", ["suho oko", "draženje oči"]),

            # Alergijski simptomi
            ("kihanje", "Kihanje", ["kiham", "smrčim"]),
            ("srbec_oci", "Srbeče oči", ["srbi oko", "srbijo oči"]),
            ("otekel_nos", "Zamašen nos", ["zamašen", "curanje"]),

            # Urgentni simptomi
            ("huda_bolecina", "Huda bolečina", ["zelo boli", "neznosno", "močna bolečina"]),
            ("krvavitev", "Krvavitev", ["krvavi", "kri", "krvavim"]),
            ("vrocina", "Vročina", ["vročina", "temperatura", "mrzlica"]),
            ("tezko_dihanje", "Težko dihanje", ["ne morem dihat", "zadihana"]),
        ]

        for sym_id, name, keywords in symptoms:
            self._add_node(GraphNode(
                id=sym_id,
                name=name,
                name_sl=name,
                node_type=NodeType.SYMPTOM,
                properties={"keywords": keywords}
            ))

        # ================================================================
        # DELI TELESA
        # ================================================================
        body_parts = [
            ("koza", "Koža", ["koža", "kožna"]),
            ("koleno", "Koleno", ["koleno", "kolena"]),
            ("hrbet", "Hrbet", ["hrbet", "hrbtenica"]),
            ("oci", "Oči", ["oči", "oko"]),
            ("rama", "Rama", ["rama", "ramena"]),
            ("roka", "Roka", ["roka", "dlani"]),
            ("noga", "Noga", ["noga", "stopalo"]),
        ]

        for bp_id, name, keywords in body_parts:
            self._add_node(GraphNode(
                id=bp_id,
                name=name,
                name_sl=name,
                node_type=NodeType.BODY_PART,
                properties={"keywords": keywords}
            ))

        # ================================================================
        # STORITVE
        # ================================================================
        services = [
            ("dermatoloski_pregled", "Dermatološki pregled", "dermatolog", ["pregled kože", "kožni pregled"]),
            ("ortopedski_pregled", "Ortopedski pregled", "ortoped", ["pregled sklepov", "pregled hrbtenice"]),
            ("okulisticni_pregled", "Okulistični pregled", "okulist", ["pregled vida", "očesni pregled"]),
            ("laserski_poseg", "Laserski poseg", "dermatolog", ["laser", "odstranitev žilic"]),
            ("estetski_poseg", "Estetski poseg", "dermatolog", ["botox", "filer"]),
            ("fizioterapija", "Fizioterapija", "fizioterapevt", ["vaje", "rehabilitacija"]),
        ]

        for srv_id, name, specialist, keywords in services:
            self._add_node(GraphNode(
                id=srv_id,
                name=name,
                name_sl=name,
                node_type=NodeType.SERVICE,
                properties={"keywords": keywords}
            ))
            # Poveži s specialistom
            self._add_edge(srv_id, specialist, "performed_by", weight=1.0)

        # ================================================================
        # PRIPRAVE
        # ================================================================
        preparations = [
            ("zdravstvena_kartica", "Zdravstvena kartica", "Prinesite osebni dokument in zdravstveno kartico"),
            ("ne_jesti", "Tešč", "Pred pregledom ne jejte vsaj 8 ur"),
            ("cista_koza", "Čista koža", "Koža naj bo čista, brez krem"),
            ("ocala_lece", "Očala/leče", "Prinesite svoja očala ali leče"),
            ("udobna_oblacila", "Udobna oblačila", "Oblecite udobna oblačila za lažji pregled"),
            ("izvidi", "Izvidi", "Prinesite morebitne stare izvide"),
        ]

        for prep_id, name, desc in preparations:
            self._add_node(GraphNode(
                id=prep_id,
                name=name,
                name_sl=name,
                node_type=NodeType.PREPARATION,
                properties={"description": desc}
            ))

        # ================================================================
        # POVEZAVE: SIMPTOM → SPECIALIST
        # ================================================================
        symptom_specialist_map = {
            # Dermatolog
            "bolecina_koze": [("dermatolog", 0.9)],
            "izpuscaj": [("dermatolog", 0.95)],
            "sprememba_koznega_znamenja": [("dermatolog", 1.0)],
            "suha_koza": [("dermatolog", 0.8)],

            # Ortoped
            "bolecina_kolena": [("ortoped", 0.95), ("fizioterapevt", 0.6)],
            "bolecina_hrbta": [("ortoped", 0.9), ("fizioterapevt", 0.7)],
            "bolecina_rame": [("ortoped", 0.9), ("fizioterapevt", 0.6)],
            "otekanje_sklepa": [("ortoped", 0.95)],
            "omejeno_gibanje": [("ortoped", 0.8), ("fizioterapevt", 0.8)],

            # Okulist
            "slab_vid": [("okulist", 1.0)],
            "rdece_oci": [("okulist", 0.9), ("alergolog", 0.4)],
            "suhe_oci": [("okulist", 0.9)],

            # Alergolog
            "kihanje": [("alergolog", 0.8), ("internist", 0.3)],
            "srbec_oci": [("alergolog", 0.85), ("okulist", 0.4)],
            "otekel_nos": [("alergolog", 0.8)],
        }

        for symptom_id, specialists in symptom_specialist_map.items():
            for spec_id, weight in specialists:
                self._add_edge(symptom_id, spec_id, "suggests_specialist", weight=weight)

        # ================================================================
        # POVEZAVE: STORITEV → PRIPRAVE
        # ================================================================
        service_preparation_map = {
            "dermatoloski_pregled": ["zdravstvena_kartica", "cista_koza"],
            "ortopedski_pregled": ["zdravstvena_kartica", "udobna_oblacila", "izvidi"],
            "okulisticni_pregled": ["zdravstvena_kartica", "ocala_lece"],
            "laserski_poseg": ["zdravstvena_kartica", "cista_koza"],
            "estetski_poseg": ["zdravstvena_kartica", "cista_koza"],
            "fizioterapija": ["zdravstvena_kartica", "udobna_oblacila"],
        }

        for service_id, preps in service_preparation_map.items():
            for prep_id in preps:
                self._add_edge(service_id, prep_id, "requires_preparation")

        # ================================================================
        # POVEZAVE: SIMPTOM → URGENTNOST
        # ================================================================
        self.urgency_map = {
            "huda_bolecina": UrgencyLevel.PRIORITY,
            "krvavitev": UrgencyLevel.URGENT,
            "vrocina": UrgencyLevel.PRIORITY,
            "tezko_dihanje": UrgencyLevel.EMERGENCY,
            "sprememba_koznega_znamenja": UrgencyLevel.SOON,
        }

    # ================================================================
    # QUERY METHODS
    # ================================================================

    def find_matching_symptoms(self, text: str) -> List[Tuple[GraphNode, float]]:
        """
        Najde simptome, ki se ujemajo z besedilom.

        Args:
            text: Besedilo za analizo

        Returns:
            Seznam (simptom, score) parov
        """
        text_lower = text.lower()
        matches = []

        for node in self.nodes.values():
            if node.node_type != NodeType.SYMPTOM:
                continue

            keywords = node.properties.get("keywords", [])
            score = 0.0

            # Check each keyword
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    score = max(score, 0.8)
                # Check node name
                if node.name_sl.lower() in text_lower:
                    score = max(score, 1.0)

            if score > 0:
                matches.append((node, score))

        # Sort by score
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def get_specialists_for_symptoms(
        self,
        symptom_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Vrne priporočene specialiste za dane simptome.

        Args:
            symptom_ids: Seznam ID-jev simptomov

        Returns:
            Seznam specialistov z relevance score
        """
        specialist_scores = {}

        for symptom_id in symptom_ids:
            # Find edges from this symptom to specialists
            for edge in self.edges:
                if edge.source_id == symptom_id and edge.relation == "suggests_specialist":
                    spec_id = edge.target_id
                    if spec_id not in specialist_scores:
                        specialist_scores[spec_id] = 0.0
                    specialist_scores[spec_id] += edge.weight

        # Build result
        results = []
        for spec_id, score in sorted(specialist_scores.items(), key=lambda x: x[1], reverse=True):
            if spec_id in self.nodes:
                node = self.nodes[spec_id]
                results.append({
                    "specialist_id": spec_id,
                    "name": node.name_sl,
                    "description": node.properties.get("description", ""),
                    "relevance_score": round(score, 2)
                })

        return results

    def get_preparations_for_service(self, service_id: str) -> List[Dict[str, Any]]:
        """
        Vrne potrebne priprave za storitev.

        Args:
            service_id: ID storitve

        Returns:
            Seznam priprav
        """
        preparations = []

        for edge in self.edges:
            if edge.source_id == service_id and edge.relation == "requires_preparation":
                prep_id = edge.target_id
                if prep_id in self.nodes:
                    node = self.nodes[prep_id]
                    preparations.append({
                        "preparation_id": prep_id,
                        "name": node.name_sl,
                        "description": node.properties.get("description", "")
                    })

        return preparations

    def get_urgency_level(self, symptom_ids: List[str]) -> Tuple[UrgencyLevel, str]:
        """
        Določi stopnjo nujnosti za simptome.

        Args:
            symptom_ids: Seznam ID-jev simptomov

        Returns:
            (UrgencyLevel, sporočilo)
        """
        max_urgency = UrgencyLevel.ROUTINE
        urgent_symptom = None

        for symptom_id in symptom_ids:
            urgency = self.urgency_map.get(symptom_id)
            if urgency and urgency.value > max_urgency.value:
                max_urgency = urgency
                urgent_symptom = symptom_id

        messages = {
            UrgencyLevel.ROUTINE: "Priporočamo načrtovan pregled.",
            UrgencyLevel.SOON: "Priporočamo pregled v naslednjih tednih.",
            UrgencyLevel.PRIORITY: "Priporočamo pregled v naslednjih dneh.",
            UrgencyLevel.URGENT: "Prosimo, poiščite pomoč danes.",
            UrgencyLevel.EMERGENCY: "NUJNO: Pokličite 112 ali pojdite na urgenco!"
        }

        return max_urgency, messages[max_urgency]

    def get_related_info(
        self,
        node_id: str,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """
        Vrne povezane informacije za vozlišče.

        Args:
            node_id: ID vozlišča
            max_depth: Maksimalna globina iskanja

        Returns:
            Povezane informacije
        """
        if node_id not in self.nodes:
            return {"error": "Node not found"}

        node = self.nodes[node_id]
        related = {
            "node": node.to_dict(),
            "specialists": [],
            "services": [],
            "preparations": [],
            "symptoms": []
        }

        # Find direct connections
        for edge in self.edges:
            if edge.source_id == node_id:
                target = self.nodes.get(edge.target_id)
                if target:
                    if target.node_type == NodeType.SPECIALIST:
                        related["specialists"].append(target.to_dict())
                    elif target.node_type == NodeType.SERVICE:
                        related["services"].append(target.to_dict())
                    elif target.node_type == NodeType.PREPARATION:
                        related["preparations"].append(target.to_dict())

            elif edge.target_id == node_id:
                source = self.nodes.get(edge.source_id)
                if source:
                    if source.node_type == NodeType.SYMPTOM:
                        related["symptoms"].append(source.to_dict())
                    elif source.node_type == NodeType.SERVICE:
                        related["services"].append(source.to_dict())

        return related

    # ================================================================
    # HIGH-LEVEL QUERY
    # ================================================================

    def query_symptoms(self, symptoms_text: str) -> Dict[str, Any]:
        """
        Izvede celotno analizo simptomov iz besedila.

        Args:
            symptoms_text: Opis simptomov

        Returns:
            {
                "detected_symptoms": [...],
                "recommended_specialists": [...],
                "urgency": {...},
                "preparations": [...],
                "contextual_info": str
            }
        """
        # 1. Find matching symptoms
        matches = self.find_matching_symptoms(symptoms_text)
        symptom_ids = [m[0].id for m in matches]

        # 2. Get recommended specialists
        specialists = self.get_specialists_for_symptoms(symptom_ids)

        # 3. Determine urgency
        urgency_level, urgency_message = self.get_urgency_level(symptom_ids)

        # 4. Get preparations if specialist found
        preparations = []
        if specialists:
            top_specialist = specialists[0]["specialist_id"]
            # Find service for this specialist
            for edge in self.edges:
                if edge.target_id == top_specialist and edge.relation == "performed_by":
                    service_id = edge.source_id
                    preparations = self.get_preparations_for_service(service_id)
                    break

        # 5. Build contextual info
        contextual_info = self._build_contextual_response(
            matches, specialists, urgency_level, urgency_message
        )

        return {
            "detected_symptoms": [
                {"name": m[0].name_sl, "confidence": m[1]}
                for m in matches
            ],
            "recommended_specialists": specialists,
            "urgency": {
                "level": urgency_level.name,
                "value": urgency_level.value,
                "message": urgency_message
            },
            "preparations": preparations,
            "contextual_info": contextual_info
        }

    def _build_contextual_response(
        self,
        symptoms: List[Tuple[GraphNode, float]],
        specialists: List[Dict],
        urgency: UrgencyLevel,
        urgency_message: str
    ) -> str:
        """Zgradi kontekstualni odgovor."""
        lines = []

        # Urgency warning if needed
        if urgency.value >= UrgencyLevel.URGENT.value:
            lines.append(f"⚠️ **{urgency_message}**")
            lines.append("")

        # Symptoms summary
        if symptoms:
            symptom_names = [s[0].name_sl for s in symptoms[:3]]
            lines.append(f"Na podlagi opisanih simptomov ({', '.join(symptom_names)}):")
            lines.append("")

        # Specialist recommendations
        if specialists:
            top_spec = specialists[0]
            lines.append(f"Priporočam obisk pri **{top_spec['name']}**u.")

            if len(specialists) > 1:
                alt_specs = [s['name'] for s in specialists[1:3]]
                lines.append(f"Alternativno: {', '.join(alt_specs)}.")

        # Urgency advice
        if urgency.value < UrgencyLevel.URGENT.value:
            lines.append("")
            lines.append(urgency_message)

        return "\n".join(lines)


# Singleton instance
_knowledge_graph = None


def get_knowledge_graph() -> KnowledgeGraph:
    """Vrne singleton instance."""
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = KnowledgeGraph()
    return _knowledge_graph
