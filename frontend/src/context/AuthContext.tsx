import React, { createContext, useContext, useState, useEffect } from 'react';
import { Role, User } from '../types';
import { apiGetMe, apiLogin, clearAuthToken, getAuthToken, setAuthToken, apiCreateOrder } from '../services/api';
import { flushOutbox, getQueuedOrdersCount } from '../services/outbox';

interface AuthContextType {
  user: User | null;
  role: Role | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (u: string, p: string) => Promise<void>;
  logout: () => void;
  hasRole: (...roles: Role[]) => boolean;
  isOnline: boolean;
  pendingSyncCount: number;
  triggerSync: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('ota_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isOnline, setIsOnline] = useState<boolean>(navigator.onLine);
  const [pendingSyncCount, setPendingSyncCount] = useState<number>(0);

  // Update outbox count
  const updatePendingCount = async () => {
    try {
      const count = await getQueuedOrdersCount();
      setPendingSyncCount(count);
    } catch (e) {
      console.warn('Failed to read outbox count:', e);
    }
  };

  // Sync offline orders when back online
  const triggerSync = async () => {
    if (!navigator.onLine) return;
    try {
      await flushOutbox(async (order) => {
        await apiCreateOrder({
          client_uuid: order.client_uuid,
          customer_id: order.customer_id,
          notes: order.notes,
          lines: order.lines.map((l) => ({
            item_id: l.item_id,
            qty: l.qty,
            unit_price_paise: l.unit_price_paise,
          })),
        });
      });
      await updatePendingCount();
    } catch (err) {
      console.error('Outbox auto-sync error:', err);
    }
  };

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      triggerSync();
    };
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    updatePendingCount();

    // Verify token on mount
    const checkAuth = async () => {
      const token = getAuthToken();
      if (token) {
        try {
          const profile = await apiGetMe();
          setUser(profile);
          localStorage.setItem('ota_user', JSON.stringify(profile));
        } catch (err) {
          console.error('Session validation failed:', err);
          clearAuthToken();
          setUser(null);
        }
      }
      setIsLoading(false);
    };

    checkAuth();

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const login = async (username: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await apiLogin(username, password);
      setAuthToken(res.access_token);
      const profile = await apiGetMe();
      setUser(profile);
      localStorage.setItem('ota_user', JSON.stringify(profile));
      await updatePendingCount();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    clearAuthToken();
    setUser(null);
  };

  const hasRole = (...roles: Role[]) => {
    if (!user) return false;
    return roles.includes(user.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        role: user ? user.role : null,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        hasRole,
        isOnline,
        pendingSyncCount,
        triggerSync,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
