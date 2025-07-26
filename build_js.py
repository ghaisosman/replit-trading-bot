
#!/usr/bin/env python3
"""
JavaScript Babel Transpilation Script
Converts modern ES6+ JavaScript to ES5 for broader browser compatibility
"""

import subprocess
import os
import sys
from pathlib import Path

def install_babel():
    """Install Babel CLI and preset-env via npm"""
    print("📦 Installing Babel...")
    try:
        subprocess.run(['npm', 'install', '--save-dev', '@babel/cli', '@babel/core', '@babel/preset-env'], 
                      check=True, capture_output=True, text=True)
        print("✅ Babel installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Babel: {e}")
        return False

def transpile_dashboard_js():
    """Transpile JavaScript in dashboard.html"""
    print("🔄 Transpiling JavaScript...")
    
    dashboard_file = Path("templates/dashboard.html")
    if not dashboard_file.exists():
        print("❌ dashboard.html not found")
        return False
    
    # Read the dashboard file
    with open(dashboard_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract JavaScript between script tags
    import re
    script_pattern = r'<script>(.*?)</script>'
    scripts = re.findall(script_pattern, content, re.DOTALL)
    
    if not scripts:
        print("❌ No JavaScript found in dashboard.html")
        return False
    
    # Create temporary JS file
    temp_js = Path("temp_dashboard.js")
    with open(temp_js, 'w', encoding='utf-8') as f:
        f.write('\n'.join(scripts))
    
    try:
        # Transpile with Babel
        result = subprocess.run([
            'npx', 'babel', str(temp_js), 
            '--out-file', 'temp_dashboard_es5.js',
            '--presets', '@babel/preset-env'
        ], check=True, capture_output=True, text=True)
        
        # Read transpiled code
        with open('temp_dashboard_es5.js', 'r', encoding='utf-8') as f:
            transpiled_js = f.read()
        
        # Replace script content in dashboard.html
        new_content = re.sub(
            script_pattern, 
            f'<script>\n{transpiled_js}\n</script>', 
            content, 
            count=1,
            flags=re.DOTALL
        )
        
        # Write back to dashboard.html
        with open(dashboard_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("✅ JavaScript transpiled successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Babel transpilation failed: {e}")
        return False
    finally:
        # Cleanup temp files
        for temp_file in ['temp_dashboard.js', 'temp_dashboard_es5.js']:
            if os.path.exists(temp_file):
                os.remove(temp_file)

def main():
    print("🚀 BABEL TRANSPILATION SETUP")
    print("=" * 40)
    
    # Check if npm is available
    try:
        subprocess.run(['npm', '--version'], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("❌ npm not found. Please install Node.js first.")
        return False
    
    # Install Babel
    if not install_babel():
        return False
    
    # Transpile JavaScript
    if not transpile_dashboard_js():
        return False
    
    print("\n✅ Babel transpilation complete!")
    print("🌐 Your dashboard should now work in older browsers")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
