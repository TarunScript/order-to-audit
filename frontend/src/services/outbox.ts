// IndexedDB Outbox for Offline Orders
export interface QueuedOrder {
  client_uuid: string;
  customer_id: number;
  customer_name: string;
  lines: Array<{
    item_id: number;
    sku: string;
    item_name: string;
    qty: number;
    unit_price_paise?: number;
  }>;
  total_paise: number;
  notes?: string;
  created_at: string;
  sync_status: 'PENDING' | 'SYNCING' | 'FAILED';
  error_message?: string;
}

const DB_NAME = 'ota_offline_db';
const STORE_NAME = 'orders_outbox';
const DB_VERSION = 1;

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'client_uuid' });
      }
    };
  });
}

export async function queueOrder(order: QueuedOrder): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const req = store.put(order);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export async function getQueuedOrders(): Promise<QueuedOrder[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

export async function removeQueuedOrder(client_uuid: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const req = store.delete(client_uuid);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export async function getQueuedOrdersCount(): Promise<number> {
  const orders = await getQueuedOrders();
  return orders.filter(o => o.sync_status === 'PENDING').length;
}

export async function flushOutbox(apiSubmitFn: (order: QueuedOrder) => Promise<any>): Promise<{ synced: number; failed: number }> {
  const orders = await getQueuedOrders();
  let synced = 0;
  let failed = 0;

  for (const order of orders) {
    if (order.sync_status === 'SYNCING') continue;
    try {
      order.sync_status = 'SYNCING';
      await queueOrder(order);
      await apiSubmitFn(order);
      await removeQueuedOrder(order.client_uuid);
      synced++;
    } catch (err: any) {
      console.error(`Failed to sync order ${order.client_uuid}:`, err);
      order.sync_status = 'FAILED';
      order.error_message = err.message || 'Sync failed';
      await queueOrder(order);
      failed++;
    }
  }

  return { synced, failed };
}
