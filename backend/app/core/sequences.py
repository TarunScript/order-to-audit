"""Financial-year sequence allocation with row locking.

Formats:
- Invoices: INV/<FY>/<seq>  e.g. INV/2026-27/0001
- Credit notes: CN/<FY>/<seq> e.g. CN/2026-27/0001
- Production runs: PR/<FY>/<seq> or similar if needed

Indian Financial Year runs from 1 April to 31 March.
"""
from datetime import date
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Sequence


def get_current_fy(d: Optional[date] = None) -> str:
    """Compute Indian Financial Year string (e.g. '2026-27') for a given date.

    Args:
        d: Target date (defaults to today).

    Returns:
        FY string formatted as YYYY-YY (e.g. '2026-27').
    """
    if d is None:
        d = date.today()

    year = d.year
    month = d.month

    if month >= 4:
        start_year = year
        end_year = (year + 1) % 100
    else:
        start_year = year - 1
        end_year = year % 100

    return f"{start_year}-{end_year:02d}"


async def allocate_sequence(
    session: AsyncSession,
    name: str,
    fy: Optional[str] = None,
    target_date: Optional[date] = None,
    padding: int = 4,
) -> str:
    """Allocate the next sequential number with row-level locking.

    Args:
        session: Active transactional database session.
        name: Sequence identifier ('INV', 'CN', 'PR', etc.).
        fy: Optional explicit financial year. If None, derived from target_date or today.
        target_date: Date used to determine FY if fy not provided.
        padding: Zero padding width for the sequence number.

    Returns:
        Formatted sequence string, e.g. 'INV/2026-27/0001'.
    """
    if not fy:
        fy = get_current_fy(target_date)

    # Lock row for update
    stmt = (
        select(Sequence)
        .where(Sequence.name == name, Sequence.fy == fy)
        .with_for_update()
    )
    result = await session.execute(stmt)
    seq_row = result.scalar_one_or_none()

    if seq_row is None:
        val = 1
        seq_row = Sequence(name=name, fy=fy, next_value=2)
        session.add(seq_row)
        await session.flush()
    else:
        val = seq_row.next_value
        seq_row.next_value += 1
        await session.flush()

    formatted_num = str(val).zfill(padding)
    return f"{name}/{fy}/{formatted_num}"
