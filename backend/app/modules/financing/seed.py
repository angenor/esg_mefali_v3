"""Seed des donnees de financement vert : 12 fonds, 14+ intermediaires, liaisons et embeddings."""

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.financing import (
    AccessType,
    FinancingChunk,
    FinancingSourceType,
    Fund,
    FundIntermediary,
    FundMatch,
    FundStatus,
    FundType,
    Intermediary,
    IntermediaryType,
    MatchStatus,
    OrganizationType,
)

logger = logging.getLogger(__name__)

# --- IDs stables pour les liaisons ---
FUND_IDS = {name: uuid.uuid5(uuid.NAMESPACE_DNS, f"fund.{name}") for name in [
    "gcf", "fem", "fonds_adaptation", "boad_ligne_verte", "bad_sefa", "bidc",
    "sunref", "fnde", "gold_standard", "verra", "ifc_green_bond", "bceao_refinancement",
]}
INTERMEDIARY_IDS = {name: uuid.uuid5(uuid.NAMESPACE_DNS, f"intermediary.{name}") for name in [
    "sib", "sgbci", "banque_atlantique_ci", "bridge_bank_ci", "coris_bank_ci",
    "ecobank_ci", "boad", "bad", "pnud_ci", "onudi_ci", "ande",
    "south_pole_africa", "ecoact_afrique", "fnde_agency",
]}


# =====================================================================
# 12 FONDS VERTS REELS
# =====================================================================

FUNDS_DATA: list[dict] = [
    {
        "id": FUND_IDS["gcf"],
        "name": "Fonds Vert pour le Climat (GCF)",
        "organization": "Green Climate Fund",
        "fund_type": FundType.multilateral,
        "description": "Le Fonds Vert pour le Climat est le plus grand fonds dedie au financement climatique dans les pays en developpement. Il finance des projets d'attenuation et d'adaptation au changement climatique, avec un accent sur les pays les plus vulnerables. Les PME africaines peuvent y acceder via des entites accreditees nationales ou internationales.",
        "website_url": "https://www.greenclimate.fund",
        "contact_info": {"email": "info@gcfund.org", "phone": "+82-32-458-6059"},
        "eligibility_criteria": {
            "min_revenue": 0,
            "legal_status": ["SARL", "SA", "SAS", "cooperative"],
            "min_employees": 1,
            "climate_impact_required": True,
            "country_eligibility": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Togo", "Benin", "Niger", "Guinee"],
        },
        "sectors_eligible": ["energie", "agriculture", "foret", "eau", "transport", "industrie", "batiment"],
        "min_amount_xof": 328000000,
        "max_amount_xof": 164000000000,
        "required_documents": ["business_plan", "etude_impact_environnemental", "plan_adaptation_climatique", "etats_financiers", "lettre_engagement_entite_accreditee"],
        "esg_requirements": {"min_score": 50, "environmental_criteria": ["plan_climat", "mesure_emissions"]},
        "status": FundStatus.active,
        "access_type": AccessType.intermediary_required,
        "intermediary_type": IntermediaryType.accredited_entity,
        "application_process": [
            {"step": 1, "title": "Identifier une entite accreditee", "description": "Contacter la BOAD, BAD ou PNUD pour le portage du projet"},
            {"step": 2, "title": "Preparation du concept note", "description": "Rediger une note conceptuelle avec l'entite accreditee"},
            {"step": 3, "title": "Soumission au GCF", "description": "L'entite accreditee soumet au secretariat du GCF"},
            {"step": 4, "title": "Evaluation et approbation", "description": "Le Board du GCF evalue et approuve (2-3 cycles/an)"},
            {"step": 5, "title": "Decaissement", "description": "Les fonds sont decaisses via l'entite accreditee"},
        ],
        "typical_timeline_months": 18,
        "success_tips": "Privilegiez un projet avec un fort impact climatique mesurable. Les projets d'adaptation en zone sahelienne sont prioritaires. Preparez des indicateurs quantitatifs solides (tCO2e evitees, hectares restaures, beneficiaires directs).",
    },
    {
        "id": FUND_IDS["fem"],
        "name": "Fonds pour l'Environnement Mondial (FEM/GEF)",
        "organization": "Global Environment Facility",
        "fund_type": FundType.multilateral,
        "description": "Le FEM finance des projets qui generent des benefices environnementaux mondiaux dans les domaines de la biodiversite, du changement climatique, de la degradation des terres, des eaux internationales et des polluants chimiques. Il travaille via des agences d'execution comme le PNUD, la Banque mondiale et l'ONUDI.",
        "website_url": "https://www.thegef.org",
        "contact_info": {"email": "secretariat@thegef.org"},
        "eligibility_criteria": {
            "min_revenue": 0,
            "legal_status": ["SARL", "SA", "SAS", "cooperative", "association"],
            "country_eligibility": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Togo", "Benin", "Niger", "Guinee"],
        },
        "sectors_eligible": ["biodiversite", "energie", "foret", "eau", "agriculture", "industrie"],
        "min_amount_xof": 164000000,
        "max_amount_xof": 32800000000,
        "required_documents": ["concept_note", "plan_projet", "etude_impact", "etats_financiers", "lettre_gouvernement"],
        "esg_requirements": {"min_score": 40, "environmental_criteria": ["impact_biodiversite", "plan_climat"]},
        "status": FundStatus.active,
        "access_type": AccessType.intermediary_required,
        "intermediary_type": IntermediaryType.implementation_agency,
        "application_process": [
            {"step": 1, "title": "Contacter l'agence d'execution", "description": "PNUD, Banque mondiale ou ONUDI au niveau national"},
            {"step": 2, "title": "Preparation du PIF", "description": "Rediger le Project Identification Form avec l'agence"},
            {"step": 3, "title": "Approbation nationale", "description": "Obtenir l'aval du point focal operationnel national"},
            {"step": 4, "title": "Soumission au FEM", "description": "L'agence soumet au secretariat du FEM"},
            {"step": 5, "title": "Evaluation et decaissement", "description": "Evaluation par le STAP puis decaissement"},
        ],
        "typical_timeline_months": 24,
        "success_tips": "Les projets multi-pays ou regionaux ont plus de chances. Insistez sur les co-benefices (biodiversite + climat + communautes). Le FEM favorise les projets innovants avec potentiel de repliquabilite.",
    },
    {
        "id": FUND_IDS["fonds_adaptation"],
        "name": "Fonds d'Adaptation au Changement Climatique",
        "organization": "Adaptation Fund",
        "fund_type": FundType.multilateral,
        "description": "Le Fonds d'Adaptation finance des projets concrets d'adaptation au changement climatique dans les pays en developpement vulnerables. Il est connu pour son acces direct national, permettant aux entites nationales accreditees de soumettre directement des projets.",
        "website_url": "https://www.adaptation-fund.org",
        "contact_info": {"email": "afbsec@adaptation-fund.org"},
        "eligibility_criteria": {
            "min_revenue": 0,
            "legal_status": ["SARL", "SA", "SAS", "cooperative", "association"],
            "adaptation_focus_required": True,
            "country_eligibility": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Togo", "Benin", "Niger", "Guinee"],
        },
        "sectors_eligible": ["agriculture", "eau", "sante", "infrastructure", "foret", "zones_cotieres"],
        "min_amount_xof": 65600000,
        "max_amount_xof": 6560000000,
        "required_documents": ["concept_note", "proposition_complete", "etude_vulnerabilite", "plan_adaptation", "budget_detaille"],
        "esg_requirements": {"min_score": 35, "environmental_criteria": ["vulnerabilite_climatique", "plan_adaptation"]},
        "status": FundStatus.active,
        "access_type": AccessType.intermediary_required,
        "intermediary_type": IntermediaryType.accredited_entity,
        "application_process": [
            {"step": 1, "title": "Identifier l'entite accreditee nationale", "description": "Contacter l'ANDE ou equivalent national"},
            {"step": 2, "title": "Rediger le concept note", "description": "Preparer avec l'entite accreditee"},
            {"step": 3, "title": "Soumission et revue", "description": "Soumission au Board du Fonds d'Adaptation"},
            {"step": 4, "title": "Approbation et decaissement", "description": "Decaissement via l'entite accreditee"},
        ],
        "typical_timeline_months": 12,
        "success_tips": "Focalisez-vous sur l'adaptation (pas l'attenuation). Les projets impliquant les communautes locales et les femmes sont favorises. Le budget maximal par pays est de 10M USD.",
    },
    {
        "id": FUND_IDS["boad_ligne_verte"],
        "name": "BOAD - Ligne de Credit Verte",
        "organization": "Banque Ouest Africaine de Developpement (BOAD)",
        "fund_type": FundType.regional,
        "description": "La BOAD propose des lignes de credit vertes pour financer des projets d'energie renouvelable, d'efficacite energetique et d'adaptation climatique dans la zone UEMOA. Elle intervient directement pour les grands projets ou via des banques relais pour les PME.",
        "website_url": "https://www.boad.org",
        "contact_info": {"email": "boadsiege@boad.org", "phone": "+228-22-21-59-06"},
        "eligibility_criteria": {
            "min_revenue": 100000000,
            "legal_status": ["SARL", "SA", "SAS"],
            "min_employees": 5,
            "country_eligibility": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Togo", "Benin", "Niger", "Guinee-Bissau"],
        },
        "sectors_eligible": ["energie", "agriculture", "industrie", "transport", "batiment", "eau"],
        "min_amount_xof": 50000000,
        "max_amount_xof": 16400000000,
        "required_documents": ["business_plan", "etats_financiers_3ans", "etude_faisabilite", "plan_environnemental"],
        "esg_requirements": {"min_score": 45, "environmental_criteria": ["impact_climatique"]},
        "status": FundStatus.active,
        "access_type": AccessType.mixed,
        "intermediary_type": IntermediaryType.partner_bank,
        "application_process": [
            {"step": 1, "title": "Evaluer la taille du projet", "description": "Grands projets (>1Md FCFA) : candidature directe. PME : via banque relais"},
            {"step": 2, "title": "Contacter la banque relais ou la BOAD", "description": "Pour les PME, contacter SIB, SGBCI ou Ecobank"},
            {"step": 3, "title": "Montage du dossier", "description": "Business plan, etude de faisabilite, plan environnemental"},
            {"step": 4, "title": "Instruction et approbation", "description": "Evaluation par la BOAD ou la banque relais"},
            {"step": 5, "title": "Decaissement", "description": "Decaissement progressif selon les jalons du projet"},
        ],
        "typical_timeline_months": 9,
        "success_tips": "Les projets d'energie solaire et d'efficacite energetique sont prioritaires. Montrez un retour sur investissement clair. La BOAD favorise les projets avec co-financement local (30% minimum).",
    },
    {
        "id": FUND_IDS["bad_sefa"],
        "name": "BAD - Fonds SEFA (Energie Durable pour l'Afrique)",
        "organization": "Banque Africaine de Developpement (BAD)",
        "fund_type": FundType.regional,
        "description": "Le fonds SEFA de la BAD fournit des subventions et de l'assistance technique pour les projets d'energie durable en Afrique, en particulier les energies renouvelables a petite et moyenne echelle et l'acces a l'energie en zones rurales.",
        "website_url": "https://www.afdb.org/fr/topics-and-sectors/initiatives-partnerships/sustainable-energy-fund-for-africa",
        "contact_info": {"email": "sefa@afdb.org"},
        "eligibility_criteria": {
            "min_revenue": 50000000,
            "legal_status": ["SARL", "SA", "SAS", "cooperative"],
            "energy_focus_required": True,
            "country_eligibility": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Togo", "Benin", "Niger", "Guinee"],
        },
        "sectors_eligible": ["energie", "electrification_rurale"],
        "min_amount_xof": 32800000,
        "max_amount_xof": 3280000000,
        "required_documents": ["business_plan", "etude_technique", "plan_financier", "analyse_impact_social"],
        "esg_requirements": {"min_score": 40, "environmental_criteria": ["impact_energetique", "acces_energie"]},
        "status": FundStatus.active,
        "access_type": AccessType.intermediary_required,
        "intermediary_type": IntermediaryType.accredited_entity,
        "application_process": [
            {"step": 1, "title": "Contacter le bureau BAD regional", "description": "Bureau BAD a Abidjan pour la Cote d'Ivoire"},
            {"step": 2, "title": "Soumission du concept", "description": "Envoyer une note conceptuelle au SEFA"},
            {"step": 3, "title": "Due diligence", "description": "Evaluation technique et financiere par la BAD"},
            {"step": 4, "title": "Approbation et structuration", "description": "Structuration du financement (subvention + pret)"},
        ],
        "typical_timeline_months": 12,
        "success_tips": "SEFA finance principalement la phase de preparation des projets. Presentez un plan de financement mixte (subvention SEFA + pret commercial). Les projets d'electrification rurale ont priorite.",
    },
    {
        "id": FUND_IDS["bidc"],
        "name": "BIDC - Pret Vert PME",
        "organization": "Banque d'Investissement et de Developpement de la CEDEAO (BIDC)",
        "fund_type": FundType.regional,
        "description": "La BIDC offre des prets a taux preferentiels pour les PME de la CEDEAO qui investissent dans des projets verts : energie renouvelable, agriculture durable, gestion des dechets et industrie propre.",
        "website_url": "https://bidc-ebid.org",
        "contact_info": {"email": "info@bidc-ebid.org", "phone": "+228-22-21-68-64"},
        "eligibility_criteria": {
            "min_revenue": 100000000,
            "legal_status": ["SARL", "SA", "SAS"],
            "min_employees": 10,
            "country_eligibility": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Togo", "Benin", "Niger", "Guinee", "Ghana", "Nigeria"],
        },
        "sectors_eligible": ["energie", "agriculture", "dechets", "industrie", "transport"],
        "min_amount_xof": 100000000,
        "max_amount_xof": 8200000000,
        "required_documents": ["business_plan", "etats_financiers_3ans", "etude_impact", "garanties"],
        "esg_requirements": {"min_score": 40, "environmental_criteria": ["plan_vert"]},
        "status": FundStatus.active,
        "access_type": AccessType.mixed,
        "intermediary_type": IntermediaryType.partner_bank,
        "application_process": [
            {"step": 1, "title": "Contact direct ou via banque partenaire", "description": "La BIDC accepte les candidatures directes et via banques partenaires"},
            {"step": 2, "title": "Constitution du dossier", "description": "Business plan, garanties, etude d'impact"},
            {"step": 3, "title": "Instruction", "description": "Evaluation par le departement des prets de la BIDC"},
            {"step": 4, "title": "Approbation et decaissement", "description": "Comite de credit puis decaissement"},
        ],
        "typical_timeline_months": 8,
        "success_tips": "La BIDC valorise les projets createurs d'emplois dans la zone CEDEAO. Presentez clairement l'impact en termes d'emplois directs et indirects. Les garanties solides accelerent le processus.",
    },
    {
        "id": FUND_IDS["sunref"],
        "name": "SUNREF (AFD/Proparco)",
        "organization": "AFD / Proparco",
        "fund_type": FundType.regional,
        "description": "SUNREF est une ligne de credit verte de l'AFD et Proparco distribuee via des banques partenaires locales. Elle finance des investissements verts des entreprises : efficacite energetique, energies renouvelables, batiments verts et adaptation climatique. Les PME accedent au financement via leur banque habituelle si celle-ci est partenaire SUNREF.",
        "website_url": "https://www.sunref.org",
        "contact_info": {"email": "sunref@afd.fr"},
        "eligibility_criteria": {
            "min_revenue": 10000000,
            "legal_status": ["SARL", "SA", "SAS"],
            "green_investment_required": True,
            "country_eligibility": ["Cote d'Ivoire", "Senegal", "Cameroun"],
        },
        "sectors_eligible": ["energie", "agriculture", "industrie", "batiment", "transport"],
        "min_amount_xof": 5000000,
        "max_amount_xof": 500000000,
        "required_documents": ["business_plan", "etats_financiers", "devis_investissement_vert", "esg_report"],
        "esg_requirements": {"min_score": 40, "environmental_criteria": ["investissement_vert"]},
        "status": FundStatus.active,
        "access_type": AccessType.intermediary_required,
        "intermediary_type": IntermediaryType.partner_bank,
        "application_process": [
            {"step": 1, "title": "Contact banque partenaire", "description": "Contacter SIB, SGBCI, Banque Atlantique CI ou Bridge Bank CI"},
            {"step": 2, "title": "Montage dossier credit", "description": "La banque monte le dossier avec le volet SUNREF"},
            {"step": 3, "title": "Validation SUNREF", "description": "Le consultant SUNREF valide l'eligibilite verte du projet"},
            {"step": 4, "title": "Deblocage du credit", "description": "La banque debloque le credit a taux bonifie"},
        ],
        "typical_timeline_months": 4,
        "success_tips": "SUNREF offre des taux d'interet bonifies (2-3 points en dessous du marche). Presentez un projet d'investissement vert clair avec un retour energetique mesurable. L'accompagnement technique SUNREF est gratuit.",
    },
    {
        "id": FUND_IDS["fnde"],
        "name": "FNDE - Fonds National pour le Developpement de l'Environnement",
        "organization": "Ministere de l'Environnement - Cote d'Ivoire",
        "fund_type": FundType.national,
        "description": "Le FNDE est le fonds national ivoirien dedie au financement de projets environnementaux. Il offre des subventions et prets a taux reduit pour les PME ivoiriennes investissant dans la protection de l'environnement, la gestion des dechets, les energies renouvelables et l'agriculture durable.",
        "website_url": "https://fnde.ci",
        "contact_info": {"email": "info@fnde.ci", "phone": "+225-27-22-44-28-07", "address": "Cocody, Abidjan, Cote d'Ivoire"},
        "eligibility_criteria": {
            "min_revenue": 5000000,
            "legal_status": ["SARL", "SA", "SAS", "cooperative", "association"],
            "country_eligibility": ["Cote d'Ivoire"],
        },
        "sectors_eligible": ["environnement", "dechets", "energie", "agriculture", "eau", "foret"],
        "min_amount_xof": 1000000,
        "max_amount_xof": 100000000,
        "required_documents": ["business_plan", "registre_commerce", "etude_impact_simplifie"],
        "esg_requirements": {"min_score": 25, "environmental_criteria": ["impact_environnemental"]},
        "status": FundStatus.active,
        "access_type": AccessType.direct,
        "intermediary_type": None,
        "application_process": [
            {"step": 1, "title": "Retirer le dossier", "description": "Telecharger ou retirer le formulaire au siege du FNDE a Cocody"},
            {"step": 2, "title": "Constituer le dossier", "description": "Business plan, registre de commerce, etude d'impact simplifiee"},
            {"step": 3, "title": "Soumettre le dossier", "description": "Depot au FNDE avec accuse de reception"},
            {"step": 4, "title": "Evaluation et decision", "description": "Comite technique puis comite de gestion du FNDE"},
        ],
        "typical_timeline_months": 3,
        "success_tips": "Le FNDE est le fonds le plus accessible pour les petites PME ivoiriennes. Les montants sont modestes mais le processus est rapide. Insistez sur l'impact local et les emplois verts crees.",
    },
    {
        "id": FUND_IDS["gold_standard"],
        "name": "Gold Standard - Credits Carbone",
        "organization": "Gold Standard Foundation",
        "fund_type": FundType.carbon_marketplace,
        "description": "Gold Standard certifie des projets de reduction d'emissions et genere des credits carbone certifies (VERs). Les PME africaines peuvent developper des projets (fours ameliores, solaire, biomasse) et vendre les credits sur le marche volontaire du carbone.",
        "website_url": "https://www.goldstandard.org",
        "contact_info": {"email": "info@goldstandard.org"},
        "eligibility_criteria": {
            "min_revenue": 0,
            "legal_status": ["SARL", "SA", "SAS", "cooperative", "association"],
            "measurable_emission_reductions_required": True,
        },
        "sectors_eligible": ["energie", "foret", "agriculture", "dechets", "eau"],
        "min_amount_xof": 0,
        "max_amount_xof": None,
        "required_documents": ["project_design_document", "monitoring_plan", "validation_report"],
        "esg_requirements": {"min_score": 50, "environmental_criteria": ["reduction_emissions_mesurable", "co_benefices_odd"]},
        "status": FundStatus.active,
        "access_type": AccessType.intermediary_required,
        "intermediary_type": IntermediaryType.project_developer,
        "application_process": [
            {"step": 1, "title": "Identifier un developpeur carbone", "description": "Contacter South Pole, EcoAct ou un developpeur local"},
            {"step": 2, "title": "Rediger le PDD", "description": "Project Design Document avec methodologie Gold Standard"},
            {"step": 3, "title": "Validation par auditeur", "description": "Audit par un organisme accredite (DOE)"},
            {"step": 4, "title": "Enregistrement Gold Standard", "description": "Enregistrement officiel du projet"},
            {"step": 5, "title": "Monitoring et emission de credits", "description": "Suivi annuel et emission de VERs"},
        ],
        "typical_timeline_months": 12,
        "success_tips": "Les projets de fours ameliores et de solaire domestique sont les plus courants en Afrique de l'Ouest. Le developpeur carbone prend en charge les couts initiaux en echange d'une part des credits generes.",
    },
    {
        "id": FUND_IDS["verra"],
        "name": "Verra (VCS) - Credits Carbone Certifies",
        "organization": "Verra",
        "fund_type": FundType.carbon_marketplace,
        "description": "Verra gere le Verified Carbon Standard (VCS), le plus grand programme de credits carbone au monde. Les projets certifies VCS generent des Verified Carbon Units (VCUs) echangeables sur le marche volontaire du carbone.",
        "website_url": "https://verra.org",
        "contact_info": {"email": "info@verra.org"},
        "eligibility_criteria": {
            "min_revenue": 0,
            "legal_status": ["SARL", "SA", "SAS", "cooperative"],
            "measurable_emission_reductions_required": True,
        },
        "sectors_eligible": ["energie", "foret", "agriculture", "dechets", "industrie"],
        "min_amount_xof": 0,
        "max_amount_xof": None,
        "required_documents": ["project_description", "monitoring_report", "verification_report"],
        "esg_requirements": {"min_score": 45, "environmental_criteria": ["reduction_emissions_mesurable"]},
        "status": FundStatus.active,
        "access_type": AccessType.intermediary_required,
        "intermediary_type": IntermediaryType.project_developer,
        "application_process": [
            {"step": 1, "title": "Engager un developpeur carbone", "description": "South Pole Africa, EcoAct Afrique ou developpeur local"},
            {"step": 2, "title": "Preparer la description du projet", "description": "Selon la methodologie VCS applicable"},
            {"step": 3, "title": "Validation", "description": "Audit par un organisme VVB accredite"},
            {"step": 4, "title": "Enregistrement Verra", "description": "Enregistrement sur le registre Verra"},
            {"step": 5, "title": "Verification et emission de VCUs", "description": "Verification periodique et emission de credits"},
        ],
        "typical_timeline_months": 14,
        "success_tips": "Verra accepte des methodologies plus variees que Gold Standard. Les projets REDD+ (forets) et les projets agricoles (riz, biochar) sont prometteurs en Afrique de l'Ouest.",
    },
    {
        "id": FUND_IDS["ifc_green_bond"],
        "name": "IFC - Obligations Vertes / Green Bond",
        "organization": "International Finance Corporation (IFC / Banque mondiale)",
        "fund_type": FundType.multilateral,
        "description": "L'IFC emet des obligations vertes dont les fonds sont alloues a des projets climatiques dans les pays en developpement. Les PME peuvent acceder au financement via des lignes de credit IFC distribuees par des banques partenaires locales.",
        "website_url": "https://www.ifc.org",
        "contact_info": {"email": "ifc.org/contacts"},
        "eligibility_criteria": {
            "min_revenue": 200000000,
            "legal_status": ["SARL", "SA", "SAS"],
            "min_employees": 20,
            "country_eligibility": ["Cote d'Ivoire", "Senegal", "Ghana", "Nigeria", "Kenya"],
        },
        "sectors_eligible": ["energie", "industrie", "batiment", "agriculture", "transport"],
        "min_amount_xof": 164000000,
        "max_amount_xof": 16400000000,
        "required_documents": ["business_plan", "etats_financiers_audites", "etude_impact", "plan_vert"],
        "esg_requirements": {"min_score": 55, "environmental_criteria": ["plan_climat", "reporting_environnemental"]},
        "status": FundStatus.active,
        "access_type": AccessType.intermediary_required,
        "intermediary_type": IntermediaryType.partner_bank,
        "application_process": [
            {"step": 1, "title": "Contacter la banque partenaire IFC", "description": "Ecobank, SGBCI ou banque ayant une ligne IFC"},
            {"step": 2, "title": "Evaluation creditrice", "description": "La banque evalue la solvabilite et l'eligibilite verte"},
            {"step": 3, "title": "Soumission a l'IFC", "description": "La banque soumet le dossier a l'IFC pour validation"},
            {"step": 4, "title": "Decaissement", "description": "Decaissement via la banque partenaire"},
        ],
        "typical_timeline_months": 10,
        "success_tips": "L'IFC cible les entreprises de taille moyenne avec un chiffre d'affaires significatif. Presentez des etats financiers audites et un plan de croissance verte solide.",
    },
    {
        "id": FUND_IDS["bceao_refinancement"],
        "name": "BCEAO - Mecanisme de Refinancement Vert",
        "organization": "Banque Centrale des Etats de l'Afrique de l'Ouest (BCEAO)",
        "fund_type": FundType.private,
        "description": "La BCEAO a mis en place un mecanisme de refinancement vert qui permet aux banques commerciales de la zone UEMOA d'obtenir des conditions preferentielles pour les prets verts accordes aux PME. Les entreprises en beneficient via leur banque commerciale sous forme de taux d'interet reduits.",
        "website_url": "https://www.bceao.int",
        "contact_info": {"email": "courrier@bceao.int", "phone": "+221-33-839-05-00"},
        "eligibility_criteria": {
            "min_revenue": 10000000,
            "legal_status": ["SARL", "SA", "SAS"],
            "country_eligibility": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Togo", "Benin", "Niger", "Guinee-Bissau"],
            "taxonomie_verte_uemoa_required": True,
        },
        "sectors_eligible": ["energie", "agriculture", "industrie", "batiment", "transport", "dechets"],
        "min_amount_xof": 5000000,
        "max_amount_xof": 1000000000,
        "required_documents": ["business_plan", "etats_financiers", "classification_taxonomie_verte"],
        "esg_requirements": {"min_score": 35, "environmental_criteria": ["conformite_taxonomie_verte_uemoa"]},
        "status": FundStatus.active,
        "access_type": AccessType.intermediary_required,
        "intermediary_type": IntermediaryType.partner_bank,
        "application_process": [
            {"step": 1, "title": "Contacter votre banque", "description": "Verifier que votre banque participe au mecanisme BCEAO"},
            {"step": 2, "title": "Classifier le projet", "description": "Verifier que le projet est eligible a la taxonomie verte UEMOA"},
            {"step": 3, "title": "Monter le dossier de credit", "description": "Dossier standard avec mention du volet vert BCEAO"},
            {"step": 4, "title": "Approbation et taux bonifie", "description": "La banque accorde le credit a taux reduit grace au refinancement BCEAO"},
        ],
        "typical_timeline_months": 3,
        "success_tips": "Le mecanisme BCEAO est le plus accessible car il passe par votre banque habituelle. Verifiez que votre projet respecte la taxonomie verte UEMOA. Les taux bonifies representent une economie de 1-2 points de pourcentage.",
    },
]


# =====================================================================
# 14+ INTERMEDIAIRES REELS
# =====================================================================

INTERMEDIARIES_DATA: list[dict] = [
    {
        "id": INTERMEDIARY_IDS["sib"],
        "name": "SIB (Societe Ivoirienne de Banque)",
        "intermediary_type": IntermediaryType.partner_bank,
        "organization_type": OrganizationType.bank,
        "description": "Filiale du groupe Attijariwafa Bank, la SIB est l'une des principales banques commerciales de Cote d'Ivoire. Elle est partenaire SUNREF et participe au mecanisme de refinancement vert de la BCEAO.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://www.sib.ci",
        "contact_email": "info@sib.ci",
        "contact_phone": "+225-27-20-20-00-00",
        "physical_address": "34, Boulevard de la Republique, Plateau, Abidjan, Cote d'Ivoire",
        "accreditations": ["SUNREF", "BCEAO refinancement vert"],
        "services_offered": {"credit_evaluation": True, "technical_assistance": True, "green_credit_line": True, "account_management": True},
        "typical_fees": "Taux d'interet bonifie SUNREF : 7-9% (vs 12-14% marche). Frais de dossier standard.",
        "eligibility_for_sme": {"min_revenue": 10000000, "account_required": True, "guarantees": "Garantie sur actifs ou caution solidaire"},
    },
    {
        "id": INTERMEDIARY_IDS["sgbci"],
        "name": "SGBCI (Societe Generale Cote d'Ivoire)",
        "intermediary_type": IntermediaryType.partner_bank,
        "organization_type": OrganizationType.bank,
        "description": "Filiale de la Societe Generale, la SGBCI est une banque majeure en Cote d'Ivoire avec un departement PME developpe. Partenaire SUNREF et participant au mecanisme BCEAO.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://www.sgbci.ci",
        "contact_email": "contact@sgbci.ci",
        "contact_phone": "+225-27-20-20-12-34",
        "physical_address": "5-7, Avenue Joseph Anoma, Plateau, Abidjan, Cote d'Ivoire",
        "accreditations": ["SUNREF", "BCEAO refinancement vert", "IFC ligne verte"],
        "services_offered": {"credit_evaluation": True, "technical_assistance": True, "green_credit_line": True, "account_management": True, "trade_finance": True},
        "typical_fees": "Taux SUNREF : 7-9%. Frais dossier : 1-2% du montant.",
        "eligibility_for_sme": {"min_revenue": 20000000, "account_required": True},
    },
    {
        "id": INTERMEDIARY_IDS["banque_atlantique_ci"],
        "name": "Banque Atlantique Cote d'Ivoire",
        "intermediary_type": IntermediaryType.partner_bank,
        "organization_type": OrganizationType.bank,
        "description": "Filiale du groupe Atlantic Financial Group, Banque Atlantique CI est partenaire SUNREF et active dans le financement vert des PME ivoiriennes.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://www.banqueatlantique.net",
        "contact_email": "info@banqueatlantique.net",
        "contact_phone": "+225-27-20-31-14-00",
        "physical_address": "Avenue Noguesse Abrogoua, Plateau, Abidjan, Cote d'Ivoire",
        "accreditations": ["SUNREF", "BCEAO refinancement vert"],
        "services_offered": {"credit_evaluation": True, "green_credit_line": True, "account_management": True},
        "typical_fees": "Taux SUNREF : 8-10%. Frais dossier : 1%.",
        "eligibility_for_sme": {"min_revenue": 10000000, "account_required": True},
    },
    {
        "id": INTERMEDIARY_IDS["bridge_bank_ci"],
        "name": "Bridge Bank Group CI",
        "intermediary_type": IntermediaryType.partner_bank,
        "organization_type": OrganizationType.bank,
        "description": "Bridge Bank est une banque specialisee dans le financement des PME en Cote d'Ivoire. Partenaire SUNREF, elle offre un accompagnement rapproche pour les projets verts.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://www.bridgebankgroup.com",
        "contact_email": "contact@bridgebankgroup.com",
        "contact_phone": "+225-27-20-25-05-05",
        "physical_address": "Immeuble Alliance, Rue des Jardins, Cocody, Abidjan, Cote d'Ivoire",
        "accreditations": ["SUNREF"],
        "services_offered": {"credit_evaluation": True, "technical_assistance": True, "green_credit_line": True, "sme_coaching": True},
        "typical_fees": "Taux SUNREF : 8-10%. Accompagnement PME inclus.",
        "eligibility_for_sme": {"min_revenue": 5000000, "account_required": True},
    },
    {
        "id": INTERMEDIARY_IDS["coris_bank_ci"],
        "name": "Coris Bank International CI",
        "intermediary_type": IntermediaryType.partner_bank,
        "organization_type": OrganizationType.bank,
        "description": "Filiale ivoirienne du groupe Coris Bank (Burkina Faso), specialisee dans la banque de detail et le financement des PME en zone UEMOA.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://www.coris-bank.com",
        "contact_email": "info@corisbank.ci",
        "contact_phone": "+225-27-20-31-55-00",
        "physical_address": "Boulevard Carde, Plateau, Abidjan, Cote d'Ivoire",
        "accreditations": ["BCEAO refinancement vert"],
        "services_offered": {"credit_evaluation": True, "green_credit_line": True, "account_management": True},
        "typical_fees": "Taux marche standard avec bonification BCEAO.",
        "eligibility_for_sme": {"min_revenue": 10000000, "account_required": True},
    },
    {
        "id": INTERMEDIARY_IDS["ecobank_ci"],
        "name": "Ecobank Cote d'Ivoire",
        "intermediary_type": IntermediaryType.partner_bank,
        "organization_type": OrganizationType.bank,
        "description": "Le groupe Ecobank est present dans 33 pays africains. Ecobank CI est partenaire de plusieurs lignes de credit vertes et dispose d'un departement PME/Entrepreneuriat.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://www.ecobank.com/ci",
        "contact_email": "eabordeaux@ecobank.com",
        "contact_phone": "+225-27-20-31-92-00",
        "physical_address": "Avenue Houdaille, Plateau, Abidjan, Cote d'Ivoire",
        "accreditations": ["BCEAO refinancement vert", "IFC ligne verte", "BOAD ligne verte"],
        "services_offered": {"credit_evaluation": True, "green_credit_line": True, "account_management": True, "trade_finance": True, "digital_banking": True},
        "typical_fees": "Taux bonifies selon ligne de credit. Frais de dossier : 1-1.5%.",
        "eligibility_for_sme": {"min_revenue": 20000000, "account_required": True},
    },
    {
        "id": INTERMEDIARY_IDS["boad"],
        "name": "BOAD (Banque Ouest Africaine de Developpement)",
        "intermediary_type": IntermediaryType.accredited_entity,
        "organization_type": OrganizationType.development_bank,
        "description": "La BOAD est l'institution de financement du developpement de l'UEMOA. Elle est entite accreditee aupres du GCF et du Fonds d'Adaptation, et gere ses propres lignes de credit vertes.",
        "country": "Togo",
        "city": "Lome",
        "website_url": "https://www.boad.org",
        "contact_email": "boadsiege@boad.org",
        "contact_phone": "+228-22-21-59-06",
        "physical_address": "68, Avenue de la Liberation, BP 1172, Lome, Togo",
        "accreditations": ["GCF entite accreditee", "Fonds Adaptation entite accreditee", "FEM agence d'execution"],
        "services_offered": {"project_development": True, "technical_assistance": True, "credit_line_management": True, "gcf_project_development": True},
        "typical_fees": "Variable selon l'instrument. Taux concessionnel pour les projets verts.",
        "eligibility_for_sme": {"min_revenue": 100000000, "via_bank_for_sme": True},
    },
    {
        "id": INTERMEDIARY_IDS["bad"],
        "name": "BAD (Banque Africaine de Developpement)",
        "intermediary_type": IntermediaryType.accredited_entity,
        "organization_type": OrganizationType.development_bank,
        "description": "La BAD est la premiere institution financiere de developpement d'Afrique. Elle est entite accreditee aupres du GCF et gere le fonds SEFA pour l'energie durable.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://www.afdb.org",
        "contact_email": "afdb@afdb.org",
        "contact_phone": "+225-27-20-26-10-20",
        "physical_address": "Avenue Joseph Anoma, 01 BP 1387, Abidjan 01, Cote d'Ivoire",
        "accreditations": ["GCF entite accreditee", "FEM agence d'execution", "Fonds Adaptation"],
        "services_offered": {"project_development": True, "technical_assistance": True, "sefa_grants": True, "gcf_project_development": True, "policy_advisory": True},
        "typical_fees": "Subventions SEFA sans remboursement. Prets a taux concessionnel.",
        "eligibility_for_sme": {"min_revenue": 50000000, "energy_focus_for_sefa": True},
    },
    {
        "id": INTERMEDIARY_IDS["pnud_ci"],
        "name": "PNUD Cote d'Ivoire",
        "intermediary_type": IntermediaryType.implementation_agency,
        "organization_type": OrganizationType.un_agency,
        "description": "Le PNUD en Cote d'Ivoire est agence d'execution du FEM et entite accreditee du Fonds d'Adaptation. Il facilite l'acces des projets ivoiriens aux financements climatiques internationaux.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://www.undp.org/fr/cote-divoire",
        "contact_email": "registry.ci@undp.org",
        "contact_phone": "+225-27-22-40-44-00",
        "physical_address": "Angle Bd Latrille et Rue J-44, Cocody, Abidjan, Cote d'Ivoire",
        "accreditations": ["FEM agence d'execution", "Fonds Adaptation entite accreditee", "GCF entite accreditee"],
        "services_offered": {"project_development": True, "technical_assistance": True, "capacity_building": True, "monitoring_evaluation": True},
        "typical_fees": "Pas de frais directs. Cout de gestion inclus dans le budget projet (7-10%).",
        "eligibility_for_sme": {"min_revenue": 0, "project_based": True},
    },
    {
        "id": INTERMEDIARY_IDS["onudi_ci"],
        "name": "ONUDI Cote d'Ivoire",
        "intermediary_type": IntermediaryType.implementation_agency,
        "organization_type": OrganizationType.un_agency,
        "description": "L'ONUDI en Cote d'Ivoire soutient le developpement industriel durable. Agence d'execution du FEM pour les projets industriels, elle aide les PME a adopter des technologies propres.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://www.unido.org",
        "contact_email": "office.cotedivoire@unido.org",
        "contact_phone": "+225-27-22-40-33-00",
        "physical_address": "Cocody, II Plateaux, Abidjan, Cote d'Ivoire",
        "accreditations": ["FEM agence d'execution"],
        "services_offered": {"technical_assistance": True, "clean_technology_transfer": True, "industrial_efficiency": True, "capacity_building": True},
        "typical_fees": "Assistance technique gratuite via projets FEM.",
        "eligibility_for_sme": {"min_revenue": 0, "industrial_focus": True},
    },
    {
        "id": INTERMEDIARY_IDS["ande"],
        "name": "ANDE (Agence Nationale de l'Environnement)",
        "intermediary_type": IntermediaryType.national_agency,
        "organization_type": OrganizationType.government_agency,
        "description": "L'ANDE est le point focal operationnel du FEM en Cote d'Ivoire et entite accreditee nationale du Fonds d'Adaptation. Elle coordonne l'acces aux financements climatiques pour le pays.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://www.ande.ci",
        "contact_email": "info@ande.ci",
        "contact_phone": "+225-27-22-44-28-88",
        "physical_address": "Cocody Riviera Bonoumin, Abidjan, Cote d'Ivoire",
        "accreditations": ["FEM point focal operationnel", "Fonds Adaptation entite accreditee nationale"],
        "services_offered": {"project_endorsement": True, "environmental_assessment": True, "fund_access_facilitation": True, "capacity_building": True},
        "typical_fees": "Service public gratuit.",
        "eligibility_for_sme": {"min_revenue": 0, "ivorian_entity_required": True},
    },
    {
        "id": INTERMEDIARY_IDS["south_pole_africa"],
        "name": "South Pole Africa",
        "intermediary_type": IntermediaryType.project_developer,
        "organization_type": OrganizationType.carbon_developer,
        "description": "South Pole est le plus grand developpeur de projets carbone au monde. Sa branche africaine accompagne les PME dans le developpement de projets certifies Gold Standard et Verra.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://www.southpole.com",
        "contact_email": "africa@southpole.com",
        "contact_phone": "+225-27-22-00-00-00",
        "physical_address": "Cocody, Abidjan, Cote d'Ivoire",
        "accreditations": ["Gold Standard developpeur accredite", "Verra developpeur accredite"],
        "services_offered": {"carbon_project_development": True, "certification_support": True, "credit_trading": True, "technical_assistance": True},
        "typical_fees": "South Pole prefinance les projets en echange de 30-50% des credits generes.",
        "eligibility_for_sme": {"min_revenue": 0, "measurable_reductions_required": True},
    },
    {
        "id": INTERMEDIARY_IDS["ecoact_afrique"],
        "name": "EcoAct Afrique",
        "intermediary_type": IntermediaryType.project_developer,
        "organization_type": OrganizationType.consulting_firm,
        "description": "EcoAct est un cabinet de conseil en strategie climat et developpeur de projets carbone present en Afrique de l'Ouest. Il accompagne les entreprises dans la mesure, reduction et compensation de leurs emissions.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://eco-act.com",
        "contact_email": "afrique@eco-act.com",
        "contact_phone": "+225-27-22-00-00-00",
        "physical_address": "Cocody, Abidjan, Cote d'Ivoire",
        "accreditations": ["Gold Standard developpeur", "Verra developpeur"],
        "services_offered": {"carbon_project_development": True, "climate_strategy": True, "emission_measurement": True, "offset_programs": True},
        "typical_fees": "Honoraires de conseil + pourcentage sur credits carbone generes.",
        "eligibility_for_sme": {"min_revenue": 0, "measurable_reductions_required": True},
    },
    {
        "id": INTERMEDIARY_IDS["fnde_agency"],
        "name": "FNDE (Fonds National Developpement Environnement)",
        "intermediary_type": IntermediaryType.national_agency,
        "organization_type": OrganizationType.government_agency,
        "description": "Le FNDE est le guichet national ivoirien pour le financement direct des projets environnementaux des PME. Il gere le fonds FNDE et facilite l'acces aux financements climatiques nationaux.",
        "country": "Cote d'Ivoire",
        "city": "Abidjan",
        "website_url": "https://fnde.ci",
        "contact_email": "info@fnde.ci",
        "contact_phone": "+225-27-22-44-28-07",
        "physical_address": "Cocody, Abidjan, Cote d'Ivoire",
        "accreditations": ["Fonds national environnement"],
        "services_offered": {"direct_funding": True, "project_evaluation": True, "environmental_monitoring": True},
        "typical_fees": "Subventions sans frais. Prets a taux reduit 5-7%.",
        "eligibility_for_sme": {"min_revenue": 5000000, "ivorian_entity_required": True},
    },
]


# =====================================================================
# ~50 LIAISONS FONDS-INTERMEDIAIRES
# =====================================================================

FUND_INTERMEDIARY_LINKS: list[dict] = [
    # GCF -> entites accreditees
    {"fund_id": FUND_IDS["gcf"], "intermediary_id": INTERMEDIARY_IDS["boad"], "role": "Entite accreditee regionale pour le portage de projets GCF en zone UEMOA", "is_primary": True, "geographic_coverage": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Togo", "Benin", "Niger"]},
    {"fund_id": FUND_IDS["gcf"], "intermediary_id": INTERMEDIARY_IDS["bad"], "role": "Entite accreditee continentale pour les projets GCF en Afrique", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso"]},
    {"fund_id": FUND_IDS["gcf"], "intermediary_id": INTERMEDIARY_IDS["pnud_ci"], "role": "Entite accreditee multilaterale pour les projets GCF en CI", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    # FEM -> agences d'execution
    {"fund_id": FUND_IDS["fem"], "intermediary_id": INTERMEDIARY_IDS["pnud_ci"], "role": "Agence d'execution FEM pour la Cote d'Ivoire", "is_primary": True, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["fem"], "intermediary_id": INTERMEDIARY_IDS["onudi_ci"], "role": "Agence d'execution FEM pour les projets industriels en CI", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["fem"], "intermediary_id": INTERMEDIARY_IDS["bad"], "role": "Agence d'execution FEM pour l'Afrique", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso"]},
    {"fund_id": FUND_IDS["fem"], "intermediary_id": INTERMEDIARY_IDS["ande"], "role": "Point focal operationnel FEM en Cote d'Ivoire (endossement obligatoire)", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    # Fonds Adaptation -> entites accreditees
    {"fund_id": FUND_IDS["fonds_adaptation"], "intermediary_id": INTERMEDIARY_IDS["ande"], "role": "Entite accreditee nationale pour le Fonds d'Adaptation en CI", "is_primary": True, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["fonds_adaptation"], "intermediary_id": INTERMEDIARY_IDS["boad"], "role": "Entite accreditee regionale pour le Fonds d'Adaptation en UEMOA", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Togo", "Benin", "Niger"]},
    {"fund_id": FUND_IDS["fonds_adaptation"], "intermediary_id": INTERMEDIARY_IDS["pnud_ci"], "role": "Entite accreditee multilaterale pour le Fonds d'Adaptation en CI", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    # BOAD Ligne Verte -> banques relais
    {"fund_id": FUND_IDS["boad_ligne_verte"], "intermediary_id": INTERMEDIARY_IDS["sib"], "role": "Banque relais pour la ligne de credit verte BOAD en CI", "is_primary": True, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["boad_ligne_verte"], "intermediary_id": INTERMEDIARY_IDS["sgbci"], "role": "Banque relais BOAD en CI", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["boad_ligne_verte"], "intermediary_id": INTERMEDIARY_IDS["ecobank_ci"], "role": "Banque relais BOAD en CI", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["boad_ligne_verte"], "intermediary_id": INTERMEDIARY_IDS["boad"], "role": "Acces direct BOAD pour les grands projets", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Togo", "Benin", "Niger"]},
    # BAD SEFA
    {"fund_id": FUND_IDS["bad_sefa"], "intermediary_id": INTERMEDIARY_IDS["bad"], "role": "Gestionnaire du fonds SEFA", "is_primary": True, "geographic_coverage": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Togo", "Benin", "Niger", "Guinee"]},
    # BIDC -> banques et direct
    {"fund_id": FUND_IDS["bidc"], "intermediary_id": INTERMEDIARY_IDS["ecobank_ci"], "role": "Banque partenaire BIDC en CI", "is_primary": True, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["bidc"], "intermediary_id": INTERMEDIARY_IDS["sgbci"], "role": "Banque partenaire BIDC en CI", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    # SUNREF -> banques partenaires
    {"fund_id": FUND_IDS["sunref"], "intermediary_id": INTERMEDIARY_IDS["sib"], "role": "Banque partenaire SUNREF en CI", "is_primary": True, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["sunref"], "intermediary_id": INTERMEDIARY_IDS["sgbci"], "role": "Banque partenaire SUNREF en CI", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["sunref"], "intermediary_id": INTERMEDIARY_IDS["banque_atlantique_ci"], "role": "Banque partenaire SUNREF en CI", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["sunref"], "intermediary_id": INTERMEDIARY_IDS["bridge_bank_ci"], "role": "Banque partenaire SUNREF en CI", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    # Gold Standard -> developpeurs carbone
    {"fund_id": FUND_IDS["gold_standard"], "intermediary_id": INTERMEDIARY_IDS["south_pole_africa"], "role": "Developpeur carbone accredite Gold Standard en Afrique de l'Ouest", "is_primary": True, "geographic_coverage": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Ghana"]},
    {"fund_id": FUND_IDS["gold_standard"], "intermediary_id": INTERMEDIARY_IDS["ecoact_afrique"], "role": "Developpeur carbone Gold Standard en Afrique de l'Ouest", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire", "Senegal"]},
    # Verra -> developpeurs carbone
    {"fund_id": FUND_IDS["verra"], "intermediary_id": INTERMEDIARY_IDS["south_pole_africa"], "role": "Developpeur carbone accredite Verra en Afrique de l'Ouest", "is_primary": True, "geographic_coverage": ["Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Ghana"]},
    {"fund_id": FUND_IDS["verra"], "intermediary_id": INTERMEDIARY_IDS["ecoact_afrique"], "role": "Developpeur carbone Verra en Afrique de l'Ouest", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire", "Senegal"]},
    # IFC Green Bond -> banques
    {"fund_id": FUND_IDS["ifc_green_bond"], "intermediary_id": INTERMEDIARY_IDS["sgbci"], "role": "Banque partenaire IFC pour la distribution de lignes vertes en CI", "is_primary": True, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["ifc_green_bond"], "intermediary_id": INTERMEDIARY_IDS["ecobank_ci"], "role": "Banque partenaire IFC en CI", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    # BCEAO Refinancement -> banques commerciales
    {"fund_id": FUND_IDS["bceao_refinancement"], "intermediary_id": INTERMEDIARY_IDS["sib"], "role": "Banque participante au mecanisme de refinancement vert BCEAO", "is_primary": True, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["bceao_refinancement"], "intermediary_id": INTERMEDIARY_IDS["sgbci"], "role": "Banque participante refinancement vert BCEAO", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["bceao_refinancement"], "intermediary_id": INTERMEDIARY_IDS["banque_atlantique_ci"], "role": "Banque participante refinancement vert BCEAO", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["bceao_refinancement"], "intermediary_id": INTERMEDIARY_IDS["coris_bank_ci"], "role": "Banque participante refinancement vert BCEAO", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["bceao_refinancement"], "intermediary_id": INTERMEDIARY_IDS["ecobank_ci"], "role": "Banque participante refinancement vert BCEAO", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
    {"fund_id": FUND_IDS["bceao_refinancement"], "intermediary_id": INTERMEDIARY_IDS["bridge_bank_ci"], "role": "Banque participante refinancement vert BCEAO", "is_primary": False, "geographic_coverage": ["Cote d'Ivoire"]},
]


def _build_chunk_text(fund: dict) -> str:
    """Construit le texte du chunk pour un fonds."""
    sectors = ", ".join(fund.get("sectors_eligible", []))
    min_amt = fund.get("min_amount_xof")
    max_amt = fund.get("max_amount_xof")
    montants = ""
    if min_amt and max_amt:
        montants = f"Montant : {min_amt:,} a {max_amt:,} FCFA."
    elif max_amt:
        montants = f"Montant maximum : {max_amt:,} FCFA."
    access = fund.get("access_type", AccessType.direct)
    access_label = {
        AccessType.direct: "Acces direct",
        AccessType.intermediary_required: "Via intermediaire",
        AccessType.mixed: "Acces mixte (direct ou intermediaire)",
    }.get(access, str(access))
    tips = fund.get("success_tips", "") or ""
    return (
        f"{fund['name']} — {fund['organization']}. "
        f"{fund['description']} "
        f"Secteurs eligibles : {sectors}. "
        f"{montants} "
        f"Mode d'acces : {access_label}. "
        f"Timeline typique : {fund.get('typical_timeline_months', '?')} mois. "
        f"{tips}"
    )


def _build_intermediary_chunk_text(inter: dict) -> str:
    """Construit le texte du chunk pour un intermediaire."""
    services = ", ".join(k for k, v in inter.get("services_offered", {}).items() if v)
    return (
        f"{inter['name']} — {inter.get('description', '')} "
        f"Type : {inter['intermediary_type'].value if hasattr(inter['intermediary_type'], 'value') else inter['intermediary_type']}. "
        f"Organisation : {inter['organization_type'].value if hasattr(inter['organization_type'], 'value') else inter['organization_type']}. "
        f"Localisation : {inter['city']}, {inter['country']}. "
        f"Services : {services}. "
        f"Frais : {inter.get('typical_fees', 'Non precise')}."
    )


async def seed_financing_data(db: AsyncSession) -> dict:
    """Insere les fonds, intermediaires, liaisons et chunks dans la BDD.

    Retourne un dict avec les compteurs d'elements inseres.
    """
    # Verifier si deja seede
    existing = await db.execute(select(Fund).limit(1))
    if existing.scalar_one_or_none() is not None:
        logger.info("Donnees financing deja presentes, seed ignore.")
        return {"funds": 0, "intermediaries": 0, "links": 0, "chunks": 0}

    # 1. Fonds
    funds = []
    for data in FUNDS_DATA:
        fund = Fund(**data)
        db.add(fund)
        funds.append(fund)
    await db.flush()
    logger.info("Seed: %d fonds inseres", len(funds))

    # 2. Intermediaires
    intermediaries = []
    for data in INTERMEDIARIES_DATA:
        inter = Intermediary(**data)
        db.add(inter)
        intermediaries.append(inter)
    await db.flush()
    logger.info("Seed: %d intermediaires inseres", len(intermediaries))

    # 3. Liaisons
    links = []
    for link_data in FUND_INTERMEDIARY_LINKS:
        link = FundIntermediary(
            fund_id=link_data["fund_id"],
            intermediary_id=link_data["intermediary_id"],
            role=link_data.get("role"),
            is_primary=link_data.get("is_primary", False),
            geographic_coverage=link_data.get("geographic_coverage", []),
        )
        db.add(link)
        links.append(link)
    await db.flush()
    logger.info("Seed: %d liaisons fonds-intermediaires inserees", len(links))

    # 4. Chunks RAG (textes — embeddings generes separement)
    chunks = []
    for data in FUNDS_DATA:
        chunk = FinancingChunk(
            source_type=FinancingSourceType.fund,
            source_id=data["id"],
            content=_build_chunk_text(data),
        )
        db.add(chunk)
        chunks.append(chunk)

    for data in INTERMEDIARIES_DATA:
        chunk = FinancingChunk(
            source_type=FinancingSourceType.intermediary,
            source_id=data["id"],
            content=_build_intermediary_chunk_text(data),
        )
        db.add(chunk)
        chunks.append(chunk)

    await db.flush()
    logger.info("Seed: %d chunks RAG inseres", len(chunks))

    await db.commit()
    return {
        "funds": len(funds),
        "intermediaries": len(intermediaries),
        "links": len(links),
        "chunks": len(chunks),
    }


async def generate_embeddings(db: AsyncSession) -> int:
    """Genere les embeddings pour les chunks financing sans embedding."""
    try:
        from langchain_openai import OpenAIEmbeddings

        from app.core.config import settings
    except ImportError:
        logger.warning("langchain_openai non disponible, embeddings ignores.")
        return 0

    if not settings.openrouter_api_key:
        logger.warning("OPENROUTER_API_KEY non configuree, embeddings ignores.")
        return 0

    embeddings_model = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=settings.openrouter_api_key,
        openai_api_base="https://openrouter.ai/api/v1",
    )

    result = await db.execute(
        select(FinancingChunk).where(FinancingChunk.embedding.is_(None))
    )
    chunks_without_embedding = result.scalars().all()

    if not chunks_without_embedding:
        logger.info("Tous les chunks financing ont deja des embeddings.")
        return 0

    texts = [c.content for c in chunks_without_embedding]
    vectors = await embeddings_model.aembed_documents(texts)

    for chunk, vector in zip(chunks_without_embedding, vectors):
        chunk.embedding = vector

    await db.flush()
    await db.commit()
    logger.info("Embeddings generes pour %d chunks financing.", len(vectors))
    return len(vectors)


async def run_seed() -> None:
    """Point d'entree pour executer le seed en standalone."""
    async with async_session_factory() as db:
        result = await seed_financing_data(db)
        print(f"Seed termine: {result}")
        if result["chunks"] > 0:
            count = await generate_embeddings(db)
            print(f"Embeddings generes: {count}")


if __name__ == "__main__":
    asyncio.run(run_seed())
