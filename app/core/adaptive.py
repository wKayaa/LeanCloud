"""Adaptive concurrency controller for httpxCloud v1"""

import asyncio
import time
from collections import deque
from typing import Dict, Optional, Deque, Any
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class ConcurrencyMetrics:
    """Metrics for adaptive concurrency control"""
    current_concurrency: int = 10000
    target_concurrency: int = 10000
    
    # Latency tracking (percentiles in ms)
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    
    # Error rates
    error_rate: float = 0.0  # Percentage of requests that error
    timeout_rate: float = 0.0  # Percentage of requests that timeout
    
    # Throughput metrics
    requests_per_sec: float = 0.0
    successful_requests_per_sec: float = 0.0
    
    # System resources
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    
    # Control state
    last_adjustment: float = 0.0
    adjustment_reason: str = ""
    
    # Recent response times for percentile calculation
    _response_times: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    _error_count: int = 0
    _timeout_count: int = 0
    _total_requests: int = 0
    _window_start: float = field(default_factory=time.time)
    
    def add_response_time(self, response_time_ms: float, success: bool = True, timeout: bool = False):
        """Add a response time measurement"""
        self._response_times.append(response_time_ms)
        self._total_requests += 1
        
        if not success:
            self._error_count += 1
        if timeout:
            self._timeout_count += 1
        
        # Update metrics periodically
        if time.time() - self._window_start > 10:  # Every 10 seconds
            self._update_metrics()
    
    def _update_metrics(self):
        """Update calculated metrics"""
        now = time.time()
        window_duration = now - self._window_start
        
        # Update rates
        if window_duration > 0:
            self.requests_per_sec = self._total_requests / window_duration
            self.successful_requests_per_sec = (self._total_requests - self._error_count) / window_duration
        
        # Update error rates
        if self._total_requests > 0:
            self.error_rate = (self._error_count / self._total_requests) * 100
            self.timeout_rate = (self._timeout_count / self._total_requests) * 100
        
        # Update latency percentiles
        if self._response_times:
            sorted_times = sorted(self._response_times)
            n = len(sorted_times)
            self.p50_latency = sorted_times[int(n * 0.5)]
            self.p95_latency = sorted_times[int(n * 0.95)]
            self.p99_latency = sorted_times[int(n * 0.99)]
        
        # Reset counters for next window
        self._error_count = 0
        self._timeout_count = 0
        self._total_requests = 0
        self._window_start = now
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "current_concurrency": self.current_concurrency,
            "target_concurrency": self.target_concurrency,
            "p50_latency": round(self.p50_latency, 2),
            "p95_latency": round(self.p95_latency, 2),
            "p99_latency": round(self.p99_latency, 2),
            "error_rate": round(self.error_rate, 2),
            "timeout_rate": round(self.timeout_rate, 2),
            "requests_per_sec": round(self.requests_per_sec, 2),
            "successful_requests_per_sec": round(self.successful_requests_per_sec, 2),
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_percent": round(self.memory_percent, 2),
            "last_adjustment": self.last_adjustment,
            "adjustment_reason": self.adjustment_reason
        }


class AdaptiveController:
    """
    Adaptive concurrency controller for httpxCloud v1
    
    Automatically adjusts concurrency based on:
    - Latency percentiles (p50, p95, p99)
    - Error rates and timeouts
    - System resource utilization
    - Target performance characteristics
    
    Phase 1: Scaffold implementation for future integration
    """
    
    def __init__(
        self,
        min_concurrency: int = 10000,
        max_concurrency: int = 100000,
        target_p50_latency: float = 100.0,  # Target p50 latency in ms
        target_p95_latency: float = 500.0,  # Target p95 latency in ms
        max_error_rate: float = 5.0,  # Max acceptable error rate (%)
        max_timeout_rate: float = 2.0,  # Max acceptable timeout rate (%)
        adjustment_interval: float = 15.0,  # Minimum seconds between adjustments
        step_size: float = 0.1  # Adjustment step size (10% by default)
    ):
        self.min_concurrency = min_concurrency
        self.max_concurrency = max_concurrency
        self.target_p50_latency = target_p50_latency
        self.target_p95_latency = target_p95_latency
        self.max_error_rate = max_error_rate
        self.max_timeout_rate = max_timeout_rate
        self.adjustment_interval = adjustment_interval
        self.step_size = step_size
        
        self.metrics = ConcurrencyMetrics(current_concurrency=min_concurrency, target_concurrency=min_concurrency)
        self._enabled = False
        self._control_task: Optional[asyncio.Task] = None
        
        logger.info("AdaptiveController initialized", 
                   min_concurrency=min_concurrency, 
                   max_concurrency=max_concurrency)
    
    async def start(self):
        """Start the adaptive controller"""
        if self._enabled:
            return
        
        self._enabled = True
        self._control_task = asyncio.create_task(self._control_loop())
        logger.info("AdaptiveController started")
    
    async def stop(self):
        """Stop the adaptive controller"""
        self._enabled = False
        if self._control_task:
            self._control_task.cancel()
            try:
                await self._control_task
            except asyncio.CancelledError:
                pass
        logger.info("AdaptiveController stopped")
    
    def record_request(self, response_time_ms: float, success: bool = True, timeout: bool = False):
        """Record a request completion"""
        self.metrics.add_response_time(response_time_ms, success, timeout)
    
    def get_current_concurrency(self) -> int:
        """Get the current recommended concurrency level"""
        return self.metrics.current_concurrency
    
    def get_metrics(self) -> ConcurrencyMetrics:
        """Get current metrics"""
        return self.metrics
    
    def override_concurrency(self, concurrency: int, reason: str = "manual_override"):
        """Manually override concurrency level"""
        concurrency = max(self.min_concurrency, min(self.max_concurrency, concurrency))
        self.metrics.current_concurrency = concurrency
        self.metrics.target_concurrency = concurrency
        self.metrics.last_adjustment = time.time()
        self.metrics.adjustment_reason = reason
        
        logger.info("Concurrency manually overridden", 
                   concurrency=concurrency, reason=reason)
    
    async def _control_loop(self):
        """Main control loop for adaptive adjustments"""
        while self._enabled:
            try:
                await self._evaluate_and_adjust()
                await asyncio.sleep(5)  # Evaluate every 5 seconds, adjust per interval
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in adaptive control loop", error=str(e))
                await asyncio.sleep(10)  # Wait longer on error
    
    async def _evaluate_and_adjust(self):
        """Evaluate current performance and adjust concurrency if needed"""
        now = time.time()
        
        # Only adjust if enough time has passed since last adjustment
        if now - self.metrics.last_adjustment < self.adjustment_interval:
            return
        
        # Skip if we don't have enough data
        if len(self.metrics._response_times) < 50:
            return
        
        current = self.metrics.current_concurrency
        adjustment_reason = None
        
        # Decision logic based on performance indicators
        if self.metrics.error_rate > self.max_error_rate:
            # Too many errors - reduce concurrency
            target = int(current * (1 - self.step_size))
            adjustment_reason = f"high_error_rate_{self.metrics.error_rate:.1f}%"
            
        elif self.metrics.timeout_rate > self.max_timeout_rate:
            # Too many timeouts - reduce concurrency
            target = int(current * (1 - self.step_size))
            adjustment_reason = f"high_timeout_rate_{self.metrics.timeout_rate:.1f}%"
            
        elif self.metrics.p95_latency > self.target_p95_latency * 2:
            # Very high p95 latency - aggressive reduction
            target = int(current * (1 - self.step_size * 2))
            adjustment_reason = f"very_high_p95_latency_{self.metrics.p95_latency:.1f}ms"
            
        elif self.metrics.p95_latency > self.target_p95_latency:
            # High p95 latency - moderate reduction
            target = int(current * (1 - self.step_size))
            adjustment_reason = f"high_p95_latency_{self.metrics.p95_latency:.1f}ms"
            
        elif self.metrics.p50_latency > self.target_p50_latency * 2:
            # Very high p50 latency - moderate reduction
            target = int(current * (1 - self.step_size))
            adjustment_reason = f"very_high_p50_latency_{self.metrics.p50_latency:.1f}ms"
            
        elif (self.metrics.p50_latency < self.target_p50_latency * 0.5 and 
              self.metrics.p95_latency < self.target_p95_latency * 0.5 and
              self.metrics.error_rate < self.max_error_rate * 0.5):
            # Performance is very good - can increase concurrency
            target = int(current * (1 + self.step_size))
            adjustment_reason = f"excellent_performance_p50_{self.metrics.p50_latency:.1f}ms"
            
        elif (self.metrics.p50_latency < self.target_p50_latency * 0.8 and 
              self.metrics.p95_latency < self.target_p95_latency * 0.8 and
              self.metrics.error_rate < self.max_error_rate * 0.8):
            # Performance is good - small increase
            target = int(current * (1 + self.step_size * 0.5))
            adjustment_reason = f"good_performance_p50_{self.metrics.p50_latency:.1f}ms"
            
        else:
            # Performance is acceptable - no adjustment needed
            return
        
        # Apply bounds
        target = max(self.min_concurrency, min(self.max_concurrency, target))
        
        # Only adjust if change is significant (at least 5% or 100 requests)
        change_percent = abs(target - current) / current
        change_absolute = abs(target - current)
        
        if change_percent < 0.05 and change_absolute < 100:
            return
        
        # Apply the adjustment
        old_concurrency = self.metrics.current_concurrency
        self.metrics.current_concurrency = target
        self.metrics.target_concurrency = target
        self.metrics.last_adjustment = now
        self.metrics.adjustment_reason = adjustment_reason
        
        logger.info("Concurrency adjusted", 
                   old_concurrency=old_concurrency,
                   new_concurrency=target,
                   reason=adjustment_reason,
                   p50_latency=self.metrics.p50_latency,
                   p95_latency=self.metrics.p95_latency,
                   error_rate=self.metrics.error_rate)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of current performance characteristics"""
        return {
            "controller_enabled": self._enabled,
            "concurrency": {
                "current": self.metrics.current_concurrency,
                "target": self.metrics.target_concurrency,
                "min": self.min_concurrency,
                "max": self.max_concurrency
            },
            "latency": {
                "p50_ms": self.metrics.p50_latency,
                "p95_ms": self.metrics.p95_latency,
                "p99_ms": self.metrics.p99_latency,
                "target_p50_ms": self.target_p50_latency,
                "target_p95_ms": self.target_p95_latency
            },
            "errors": {
                "error_rate_percent": self.metrics.error_rate,
                "timeout_rate_percent": self.metrics.timeout_rate,
                "max_error_rate_percent": self.max_error_rate,
                "max_timeout_rate_percent": self.max_timeout_rate
            },
            "throughput": {
                "requests_per_sec": self.metrics.requests_per_sec,
                "successful_requests_per_sec": self.metrics.successful_requests_per_sec
            },
            "last_adjustment": {
                "timestamp": self.metrics.last_adjustment,
                "reason": self.metrics.adjustment_reason
            }
        }
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing or scan restart)"""
        self.metrics = ConcurrencyMetrics(
            current_concurrency=self.metrics.current_concurrency,
            target_concurrency=self.metrics.target_concurrency
        )
        logger.info("AdaptiveController metrics reset")


# Global adaptive controller instance
adaptive_controller = AdaptiveController()