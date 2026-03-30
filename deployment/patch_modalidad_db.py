import paramiko
import sys

def main():
    with open('/var/www/oci-app/deployment/deploy.env', 'r') as f:
        env_vars = dict(line.strip().split('=', 1) for line in f if '=' in line and not line.startswith('#'))
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=env_vars['HOST'], username=env_vars['USER'], password=env_vars['PASSWORD'], timeout=10)
    
    print("[*] Conectado exitosamente. Aplicando parche SQL al contenedor db...")
    
    cmd_sql = '''docker exec oci-app-db-1 psql -U admin -d oci_db -c "
        ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS entrenamiento_preguntas INTEGER DEFAULT 30;
        ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS entrenamiento_minutos INTEGER DEFAULT 30;
        ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS concentracion_preguntas INTEGER DEFAULT 45;
        ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS concentracion_minutos INTEGER DEFAULT 30;
        ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS maraton_preguntas INTEGER DEFAULT 100;
        ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS maraton_minutos INTEGER DEFAULT 120;
        ALTER TABLE resultados ADD COLUMN IF NOT EXISTS modalidad_test VARCHAR(100) DEFAULT 'Entrenamiento';
    "'''
    stdin, stdout, stderr = ssh.exec_command(cmd_sql)
    print("Salida STDOUT:", stdout.read().decode())
    print("Salida STDERR:", stderr.read().decode())
    
    print("[*] Reiniciando backend para limpiar caché SQLAlchemy...")
    ssh.exec_command("docker restart oci-app-backend-1")
    ssh.close()
    
    print("[*] Parche aplicado y backend reiniciado exitosamente.")

if __name__ == '__main__':
    main()
