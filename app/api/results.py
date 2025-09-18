"""
Results API endpoints for French UI parity
Implements Résultats functionality with filtering and provider validation
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
import structlog

from ..core.auth import get_current_user, require_admin
from ..core.database import get_db_session, FindingDB
from ..core.models import Hit, ProviderStatus, ProviderPayload

logger = structlog.get_logger()

router = APIRouter()


@router.get("/results")
async def list_results(
    service: Optional[str] = Query(None, description="Filter by service (aws, sendgrid, etc.)"),
    validated: Optional[bool] = Query(None, description="Filter by validation status"),
    sort: str = Query("date_desc", description="Sort order: date_asc, date_desc"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Get paginated results list with filtering
    Supports French UI filters: Tous/Validés/Invalides, service filter, sort by date
    """
    try:
        # Build base query
        query = select(FindingDB)
        count_query = select(func.count(FindingDB.id))
        
        # Apply filters
        conditions = []
        
        if service and service.lower() != "tous":
            conditions.append(FindingDB.service == service.lower())
        
        if validated is not None:
            conditions.append(FindingDB.works == validated)
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # Apply sorting
        if sort == "date_asc":
            query = query.order_by(asc(FindingDB.first_seen))
        else:  # default to date_desc
            query = query.order_by(desc(FindingDB.first_seen))
        
        # Get total count
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get paginated results
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        findings = result.scalars().all()
        
        # Convert to Hit format with provider payload
        hits = []
        for finding in findings:
            # Create provider payload from finding data
            provider_payload = None
            if finding.evidence_masked:
                provider_payload = ProviderPayload(
                    api_key_masked=finding.evidence_masked,
                    status=ProviderStatus.VALID if finding.works else ProviderStatus.INVALID,
                    reason="Validated" if finding.works else "Invalid credentials"
                )
            
            hit = Hit(
                id=str(finding.id),
                discovered_at=finding.first_seen,
                host=finding.url.split('/')[2] if '://' in finding.url else finding.url,
                path=finding.url.split('/', 3)[3] if finding.url.count('/') > 2 else "/",
                url=finding.url,
                service=finding.service,
                validated=finding.works,
                provider_payload=provider_payload,
                evidence_ref=f"scan_{finding.scan_id}",
                # Legacy fields
                scan_id=finding.scan_id,
                crack_id=finding.crack_id,
                pattern_id=finding.pattern_id,
                evidence=finding.evidence,
                evidence_masked=finding.evidence_masked
            )
            hits.append(hit.model_dump())
        
        # Calculate counters for French UI
        validated_count = sum(1 for h in hits if h['validated'])
        invalid_count = len(hits) - validated_count
        
        return {
            "hits": hits,
            "counters": {
                "total": total,
                "valides": validated_count,
                "invalides": invalid_count
            },
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total
            }
        }
        
    except Exception as e:
        logger.error("Failed to list results", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{hit_id}")
async def get_result_details(
    hit_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> Hit:
    """Get detailed information for a specific hit"""
    try:
        # Parse UUID
        try:
            import uuid
            hit_uuid = uuid.UUID(hit_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid hit ID format")
        
        # Get finding from database
        query = select(FindingDB).where(FindingDB.id == hit_uuid)
        result = await session.execute(query)
        finding = result.scalar_one_or_none()
        
        if not finding:
            raise HTTPException(status_code=404, detail="Hit not found")
        
        # Create enhanced provider payload with more details
        provider_payload = None
        if finding.evidence_masked:
            provider_payload = ProviderPayload(
                api_key_masked=finding.evidence_masked,
                status=ProviderStatus.VALID if finding.works else ProviderStatus.INVALID,
                reason="Credentials validated successfully" if finding.works else "Invalid or expired credentials",
                quota={"used": "unknown", "limit": "unknown"} if finding.works else None,
                credits=None,  # Would be populated by real validation
                proxy_state="active" if finding.works else "inactive",
                last_checked=finding.last_seen
            )
        
        hit = Hit(
            id=str(finding.id),
            discovered_at=finding.first_seen,
            host=finding.url.split('/')[2] if '://' in finding.url else finding.url,
            path=finding.url.split('/', 3)[3] if finding.url.count('/') > 2 else "/",
            url=finding.url,
            service=finding.service,
            validated=finding.works,
            provider_payload=provider_payload,
            evidence_ref=f"scan_{finding.scan_id}",
            # Legacy fields
            scan_id=finding.scan_id,
            crack_id=finding.crack_id,
            pattern_id=finding.pattern_id,
            evidence=finding.evidence,
            evidence_masked=finding.evidence_masked
        )
        
        return hit
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get result details", hit_id=hit_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/results/purge")
async def purge_all_results(
    current_user: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Purge all results (admin-only)
    Implements "Supprimer Tout" functionality
    """
    try:
        # Count current results
        count_query = select(func.count(FindingDB.id))
        result = await session.execute(count_query)
        total_count = result.scalar() or 0
        
        if total_count == 0:
            return {"message": "No results to purge", "purged_count": 0}
        
        # Delete all findings
        await session.execute("DELETE FROM findings")
        await session.commit()
        
        logger.warning("All results purged by admin", 
                      admin_user=current_user.get('sub'),
                      purged_count=total_count)
        
        return {
            "message": f"Successfully purged {total_count} results",
            "purged_count": total_count
        }
        
    except Exception as e:
        await session.rollback()
        logger.error("Failed to purge results", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/counters")
async def get_results_counters(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> Dict[str, int]:
    """Get result counters for French UI (Validés/Invalides/Total)"""
    try:
        # Get total count
        total_query = select(func.count(FindingDB.id))
        total_result = await session.execute(total_query)
        total = total_result.scalar() or 0
        
        # Get validated count
        validated_query = select(func.count(FindingDB.id)).where(FindingDB.works == True)
        validated_result = await session.execute(validated_query)
        validated = validated_result.scalar() or 0
        
        invalid = total - validated
        
        return {
            "total": total,
            "valides": validated,
            "invalides": invalid
        }
        
    except Exception as e:
        logger.error("Failed to get result counters", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/providers")
async def get_provider_stats(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> Dict[str, int]:
    """Get hit counts by provider for tiles display"""
    try:
        # Query for provider counts
        query = select(FindingDB.service, func.count(FindingDB.id)).group_by(FindingDB.service)
        result = await session.execute(query)
        provider_counts = dict(result.fetchall())
        
        # Ensure all expected providers are present
        expected_providers = ['aws', 'sendgrid', 'sparkpost', 'twilio', 'brevo', 'mailgun']
        provider_stats = {}
        
        for provider in expected_providers:
            provider_stats[provider] = provider_counts.get(provider, 0)
        
        return provider_stats
        
    except Exception as e:
        logger.error("Failed to get provider stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))