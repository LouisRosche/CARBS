"""
Mutation Testing Configuration for CARBS

This file configures mutmut for effective mutation testing.
Mutation testing verifies that tests actually catch bugs by
introducing small changes (mutations) and checking if tests fail.

Usage:
    mutmut run                    # Run mutation testing
    mutmut results                # Show results summary
    mutmut show <mutation_id>     # Show specific mutation
    mutmut html                   # Generate HTML report

Documentation: https://mutmut.readthedocs.io/
"""

def pre_mutation(context):
    """
    Hook called before applying each mutation.
    Can be used to skip certain mutations.
    """
    # Skip mutations in certain files/patterns
    skip_patterns = [
        '__init__.py',
        'test_',
        'conftest.py',
    ]

    for pattern in skip_patterns:
        if pattern in context.filename:
            context.skip = True
            return

def post_mutation(context):
    """
    Hook called after mutation testing.
    Can be used for cleanup or reporting.
    """
    pass
