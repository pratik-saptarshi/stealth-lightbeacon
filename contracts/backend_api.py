"""Backend-owned OpenAPI contract for desktop companion integration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from utils.agent_card import build_agent_card
from utils.recon import ReconRecommendation

API_VERSION = "0.1.0"
APP_VERSION = "1.2.2"
CONTRACT_DESCRIPTION = (
    "Generated backend companion contract for Stealth Lightbeacon desktop integration."
)


def _ref(name: str) -> Dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def _capabilities_example() -> Dict[str, Any]:
    card = build_agent_card()
    return {
        "apiMode": {
            "mode": "local",
            "baseUrl": "http://127.0.0.1:8000",
            "transport": "http",
            "apiVersion": API_VERSION,
            "supportsRemote": False,
        },
        "evaluationProfiles": list(card["audits"]),
        "outputFormats": list(card["outputs"]["formats"]),
        "supportsRecon": True,
        "supportsArtifacts": True,
    }


def _recon_response_example() -> Dict[str, Any]:
    recommendation = ReconRecommendation(
        url="https://example.com",
        posture="browser",
        recommended_engine="stealth",
        confidence=0.9,
        evidence=["cloudflare", "status:403"],
        signals=["cloudflare"],
        auto_select_allowed=True,
    )
    return {
        "recommendation": recommendation.recommended_engine,
        "confidence": recommendation.confidence,
        "evidenceSummary": ", ".join(recommendation.evidence),
    }


def build_openapi_document() -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": "Stealth Lightbeacon Backend API",
            "version": API_VERSION,
            "description": CONTRACT_DESCRIPTION,
        },
        "servers": [
            {
                "url": "http://127.0.0.1:8000",
                "description": "Default local companion target",
            }
        ],
        "paths": {
            "/health": {
                "get": {
                    "operationId": "getHealth",
                    "responses": {
                        "200": {
                            "description": "Backend health status",
                            "content": {
                                "application/json": {"schema": _ref("HealthResponse")}
                            },
                        }
                    },
                }
            },
            "/capabilities": {
                "get": {
                    "operationId": "getCapabilities",
                    "responses": {
                        "200": {
                            "description": "Backend capability surface",
                            "content": {
                                "application/json": {
                                    "schema": _ref("CapabilitiesResponse"),
                                    "example": _capabilities_example(),
                                }
                            },
                        }
                    },
                }
            },
            "/evaluations": {
                "post": {
                    "operationId": "createEvaluation",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": _ref("CreateEvaluationRequest")
                            }
                        },
                    },
                    "responses": {
                        "202": {
                            "description": "Evaluation accepted",
                            "content": {
                                "application/json": {
                                    "schema": _ref("CreateEvaluationResponse")
                                }
                            },
                        },
                        "400": {
                            "description": "Invalid request",
                            "content": {
                                "application/json": {"schema": _ref("ApiError")}
                            },
                        },
                    },
                }
            },
            "/evaluations/{evaluation_id}": {
                "get": {
                    "operationId": "getEvaluationStatus",
                    "parameters": [
                        {
                            "name": "evaluation_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Evaluation status response",
                            "content": {
                                "application/json": {
                                    "schema": _ref("EvaluationStatusResponse")
                                }
                            },
                        },
                        "404": {
                            "description": "Unknown evaluation",
                            "content": {
                                "application/json": {"schema": _ref("ApiError")}
                            },
                        },
                    },
                }
            },
            "/evaluations/{evaluation_id}/result": {
                "get": {
                    "operationId": "getEvaluationResult",
                    "parameters": [
                        {
                            "name": "evaluation_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Terminal evaluation result",
                            "content": {
                                "application/json": {
                                    "schema": _ref("EvaluationResultResponse")
                                }
                            },
                        }
                    },
                }
            },
            "/evaluations/{evaluation_id}/artifacts": {
                "get": {
                    "operationId": "getEvaluationArtifacts",
                    "parameters": [
                        {
                            "name": "evaluation_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Artifact descriptors for a completed evaluation",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": _ref("ArtifactDescriptor"),
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/recon": {
                "post": {
                    "operationId": "runRecon",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": _ref("ReconRequest")}
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Recon recommendation response",
                            "content": {
                                "application/json": {
                                    "schema": _ref("ReconResponse"),
                                    "example": _recon_response_example(),
                                }
                            },
                        }
                    },
                }
            },
        },
        "components": {
            "schemas": {
                "ApiError": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["code", "message"],
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "status": {
                            "type": "integer",
                            "minimum": 100,
                            "maximum": 599,
                        },
                        "details": {"type": "string"},
                    },
                },
                "HealthResponse": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["status", "service", "apiVersion"],
                    "properties": {
                        "status": {"type": "string"},
                        "service": {"type": "string"},
                        "apiVersion": {"type": "string"},
                        "appVersion": {"type": "string"},
                    },
                },
                "ApiModeResponse": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "mode",
                        "baseUrl",
                        "transport",
                        "apiVersion",
                        "supportsRemote",
                    ],
                    "properties": {
                        "mode": {"type": "string", "enum": ["local", "remote"]},
                        "baseUrl": {"type": "string", "format": "uri"},
                        "transport": {"type": "string", "enum": ["http"]},
                        "apiVersion": {"type": "string"},
                        "supportsRemote": {"type": "boolean"},
                    },
                },
                "CapabilitiesResponse": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "apiMode",
                        "evaluationProfiles",
                        "outputFormats",
                        "supportsRecon",
                        "supportsArtifacts",
                    ],
                    "properties": {
                        "apiMode": _ref("ApiModeResponse"),
                        "evaluationProfiles": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "outputFormats": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "supportsRecon": {"type": "boolean"},
                        "supportsArtifacts": {"type": "boolean"},
                    },
                },
                "CreateEvaluationRequest": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "target",
                        "profile",
                        "outputFormats",
                        "maxDepth",
                        "maxUrls",
                        "failOnCritical",
                        "budgetGate",
                    ],
                    "properties": {
                        "target": {"type": "string"},
                        "profile": {"type": "string"},
                        "outputFormats": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string"},
                        },
                        "maxDepth": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 8,
                        },
                        "maxUrls": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5000,
                        },
                        "failOnCritical": {"type": "boolean"},
                        "budgetGate": {"type": "boolean"},
                    },
                },
                "CreateEvaluationResponse": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["evaluationId", "status"],
                    "properties": {
                        "evaluationId": {"type": "string"},
                        "status": {"type": "string"},
                        "acceptedAt": {"type": "string", "format": "date-time"},
                    },
                },
                "EvaluationStatusResponse": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["evaluationId", "status", "terminal"],
                    "properties": {
                        "evaluationId": {"type": "string"},
                        "status": {"type": "string"},
                        "stage": {"type": "string"},
                        "progressPercent": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                        },
                        "message": {"type": "string"},
                        "exitState": {
                            "type": "string",
                            "enum": ["success", "failure", "budget_breach", "cancelled"],
                        },
                        "terminal": {"type": "boolean"},
                    },
                },
                "EvaluationResultResponse": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["evaluationId", "status", "summary"],
                    "properties": {
                        "evaluationId": {"type": "string"},
                        "status": {"type": "string"},
                        "summary": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                    },
                },
                "ArtifactDescriptor": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "kind", "mediaType"],
                    "properties": {
                        "name": {"type": "string"},
                        "kind": {"type": "string"},
                        "mediaType": {"type": "string"},
                        "downloadUrl": {"type": "string", "format": "uri"},
                    },
                },
                "ReconRequest": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["target"],
                    "properties": {"target": {"type": "string"}},
                },
                "ReconResponse": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["recommendation", "confidence", "evidenceSummary"],
                    "properties": {
                        "recommendation": {"type": "string"},
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                        "evidenceSummary": {"type": "string"},
                    },
                },
            }
        },
    }
    return deepcopy(doc)
