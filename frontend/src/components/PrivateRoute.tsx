import { Navigate } from 'react-router-dom';
import { useAuth } from '../lib/AuthContext';

export function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth();
  if (loading) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgb(var(--c-bg-deep))' }}>
      <div style={{ width: 32, height: 32, border: '2px solid rgb(var(--c-accent-cyan) / 0.15)', borderTopColor: 'rgb(var(--c-accent-cyan))', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
