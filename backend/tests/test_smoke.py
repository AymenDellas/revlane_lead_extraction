
import pytest
import asyncio
from engine.enricher import generate_email_permutations
from engine.anti_block import get_random_ua, random_delay, USER_AGENTS

def test_enricher_permutations():
    """Test that email permutations are generated correctly."""
    name = "John Doe"
    domain = "example.com"
    emails = generate_email_permutations(name, domain)
    
    assert "john@example.com" in emails
    assert "john.doe@example.com" in emails
    assert "jdoe@example.com" in emails
    assert len(emails) >= 5

def test_enricher_empty_input():
    """Test handling of empty inputs."""
    assert generate_email_permutations("", "example.com") == []
    assert generate_email_permutations("John", "") == []

def test_user_agent_rotation():
    """Test that we have a pool of UAs and can pick one."""
    assert len(USER_AGENTS) > 10
    ua = get_random_ua()
    assert isinstance(ua, str)
    assert len(ua) > 10

@pytest.mark.asyncio
async def test_random_delay():
    """Test that random delay waits for at least the min duration."""
    # We use a very short delay for testing to not slow down suites
    import time
    start = time.time()
    await random_delay(0.1, 0.2)
    elapsed = time.time() - start
    assert elapsed >= 0.1
