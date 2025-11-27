"""
Agents controller module.

This module contains API controllers for AI agent-related endpoints.
"""

from app.controller.agents import lead_gen_controller

router = lead_gen_controller.router
