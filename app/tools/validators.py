from app.db.models import Order, OrderStatus


def validate_cancel_order(order: Order) -> tuple[bool, str]:
    if order.status == OrderStatus.CANCELLED.value:
        return False, "Order is already cancelled."
    
    if order.status == OrderStatus.REFUNDED.value:
        return False, "Refunded orders cannot be canceled."
    
    if order.status == OrderStatus.SHIPPED.value:
        return False, "Shipped orders cannot be cancelled."
    
    if order.status == OrderStatus.DELIVERED.value:
        return False, "Delivered orders cannot be cancelled."
    
    return True, "Order is eligable for cancellation."

def validate_refund_request(order: Order, reason:str, has_existing_refund: bool) -> tuple[bool, str]:
    if not reason or not reason.strip():
        return False, "Refund reason is required."
    
    if order.status == OrderStatus.REFUNDED.value:
        return False, "Order has already been refunded."

    if order.status == OrderStatus.CANCELLED.value:
        return False, "Cancelled orders cannot be refunded."
    
    if order.status != OrderStatus.DELIVERED.value:
        return False, "Refunds can only be requested after an order has been delivered."
    
    if has_existing_refund:
        return False, "A refund has already been requested for this order."
    
    return True, "Order is eligible for refund request."